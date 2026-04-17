---
phase: 16-graph-frontend-apis
plan: 01
subsystem: api
tags: [fastapi, mongodb, motor, pydantic, graph-rag, entities, communities, cosine-search]

# Dependency graph
requires:
  - phase: 11-community-detection
    provides: upsert_community, search_communities_by_embedding, graph collections in MongoDB
  - phase: 13-graph-rag-api
    provides: existing graph router, settings.graph_rag_enabled gating pattern, Tenant dep
  - phase: 14-surface-graph-status-via-document-api
    provides: _doc_to_response mapper pattern, .isoformat() datetime convention

provides:
  - GET /v1/graph/entities (paginated, entity_type + q name-search filters, re.escape safety)
  - GET /v1/graph/entities/{id} (detail, tenant-scope 404, no embedding field)
  - GET /v1/graph/communities (paginated, level filter, (level,title) ASC sort)
  - GET /v1/graph/communities/{id} (detail with asyncio.gather member entity expansion)
  - POST /v1/graph/search (embed query via run_in_executor, cosine-rank communities, return scores)
  - list_communities DB helper (paginated, level-filterable)
  - get_community_by_id DB helper (tenant-scoped)
  - list_entities extended with q param (re.escape regex)
  - get_entity_by_id extended with optional tenant_id
  - search_communities_by_embedding returns list[tuple[float, dict]] (was list[dict])

affects:
  - 18-entity-explorer-ui
  - 19-community-browser-ui
  - 20-graph-aware-search-ui

# Tech tracking
tech-stack:
  added: []
  patterns:
    - inline Pydantic response models in route file (D-27)
    - _entity_to_response / _community_to_summary / _community_to_detail mapper helpers
    - asyncio.gather for batch entity fetch in community detail (D-18)
    - run_in_executor + time.monotonic timing pattern for graph search (mirrors search.py)
    - re.escape for user-supplied name substring query (D-07)
    - Optional tenant_id param on get_entity_by_id for backward-compat tenant scoping (D-12)
    - (score, dict) tuple return from search_communities_by_embedding

key-files:
  created:
    - tests/test_graph_api.py
  modified:
    - src/docingest/db/graph_store.py
    - src/docingest/api/routes/graph.py
    - tests/test_graph_store.py

key-decisions:
  - "All 5 routes in existing graph.py (D-01) — no new router file"
  - "Inline Pydantic models in graph.py, not a sibling schemas module (D-27)"
  - "Entity detail passes tenant_id into get_entity_by_id selector (D-12 + Task 1 step 2)"
  - "Community detail uses asyncio.gather for parallel member entity fetch (D-18)"
  - "search_communities_by_embedding return type changed to list[tuple[float,dict]] for score surfacing (D-23 + critical constraint)"
  - "Tests call route handlers directly with explicit int params to avoid FastAPI Query wrapper type issue"

patterns-established:
  - "Route-level gating: if not settings.graph_rag_enabled: raise HTTPException(403)"
  - "Mapper helpers: _entity_to_response / _community_to_summary / _community_to_detail"
  - "Tenant scope enforcement baked into DB selector (not post-fetch check)"
  - "Paginated helpers return (docs, total) tuple — consistent with list_entities pattern"

requirements-completed: [ENT-05, COMM-UI-05, SEARCH-G-03]

# Metrics
duration: 9min
completed: 2026-04-17
---

# Phase 16 Plan 01: Graph Frontend APIs Summary

**5 graph query endpoints with Pydantic models, tenant-scoped DB helpers, cosine community search, and 14-test coverage suite**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-17T16:38:33Z
- **Completed:** 2026-04-17T16:48:12Z
- **Tasks:** 3 (Task 1: DB helpers, Task 2: Route handlers, Task 3: Tests)
- **Files modified:** 4 (graph_store.py, graph.py, test_graph_store.py, test_graph_api.py)

## Accomplishments

- Extended `graph_store.py` with 2 new helpers (`list_communities`, `get_community_by_id`), 2 extended helpers (`list_entities` + q param, `get_entity_by_id` + optional tenant_id), and changed `search_communities_by_embedding` to return `list[tuple[float, dict]]` for score surfacing
- Added 8 Pydantic response/request models and 3 mapper helpers to `graph.py`, plus 5 route handlers covering entity list/detail, community list/detail, and graph search — all gated by `settings.graph_rag_enabled` (403) and tenant-scoped via `Tenant` dependency
- Created `tests/test_graph_api.py` with 14 async tests covering pagination, filtering, name search, regex safety, tenant isolation (404), graph search with mocked embed_query, and gating; full suite (85 tests) passes with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend graph_store.py DB helpers** - `c446adb` (feat)
2. **Task 2: Add Pydantic models + 5 route handlers to graph.py** - `bd80c0c` (feat)
3. **Task 3: Write tests/test_graph_api.py** - `e8c00f4` (test)

## Files Created/Modified

- `src/docingest/db/graph_store.py` - Added `import re`, extended `list_entities` with `q` param, extended `get_entity_by_id` with optional `tenant_id`, added `list_communities` and `get_community_by_id` helpers, changed `search_communities_by_embedding` return type to `list[tuple[float, dict]]`
- `src/docingest/api/routes/graph.py` - Added 8 Pydantic models, 3 mapper helpers, 5 new route handlers; updated imports for asyncio, time, embed_query, new DB helpers
- `tests/test_graph_store.py` - Updated `test_search_communities_by_embedding` to unpack `(score, comm)` tuples from new return type
- `tests/test_graph_api.py` - New file with 14 async test functions

## Decisions Made

- Extended `get_entity_by_id` to accept optional `tenant_id` (default `None`) for backward compat with graph_builder callers, passes it in the MongoDB selector so cross-tenant ObjectId guessing returns 404
- Changed `search_communities_by_embedding` return type from `list[dict]` to `list[tuple[float, dict]]` to surface cosine scores in `CommunityMatch.score`; zero-norm fallback also updated to `[(0.0, comm)]` tuples for uniform shape
- Tests call route handlers directly (not via httpx.AsyncClient) and pass explicit `page=1, per_page=50` integer values because FastAPI `Query(1, ge=1)` objects don't support arithmetic when not resolved through the DI system

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Explicit int params required for Query-defaulted route params in direct handler calls**
- **Found during:** Task 3 (test_entity_list_filter_by_type failure)
- **Issue:** When route handlers are called directly in tests without providing `page`/`per_page`, the FastAPI `Query(1, ge=1)` annotation objects remain as-is and don't support `-` arithmetic, causing `TypeError: unsupported operand type(s) for -: 'Query' and 'int'`
- **Fix:** Updated all direct route handler calls in the test file to always pass explicit integer values for `page` and `per_page` parameters
- **Files modified:** tests/test_graph_api.py
- **Verification:** All 14 tests pass
- **Committed in:** e8c00f4 (Task 3 commit, updated before commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Minor fix in test call patterns only. No scope creep. Route code unchanged.

## Issues Encountered

None beyond the deviation documented above.

## User Setup Required

None - no external service configuration required. All changes are backend Python code using existing MongoDB infrastructure.

## Next Phase Readiness

- All 5 graph read endpoints are live and tested. Frontend phases 18 (Entity Explorer), 19 (Community Browser), and 20 (Graph-Aware Search) can now be built against these endpoints.
- Phase 17 (DOC-GRAPH UI) has no dependency on Phase 16 — uses `DocumentResponse` graph fields from Phase 14.
- No known blockers. `ruff check src/` passes, full test suite (85 tests) passes.

## Known Stubs

None — all endpoints are fully wired to MongoDB. No hardcoded/placeholder data flows to any response.

---
*Phase: 16-graph-frontend-apis*
*Completed: 2026-04-17*
