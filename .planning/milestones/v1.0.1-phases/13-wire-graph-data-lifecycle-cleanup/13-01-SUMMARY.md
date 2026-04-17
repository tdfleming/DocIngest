---
phase: 13-wire-graph-data-lifecycle-cleanup
plan: "01"
subsystem: api
tags: [fastapi, mongodb, motor, graph-rag, structlog, pytest]

# Dependency graph
requires:
  - phase: 08-graph-data-models
    provides: delete_doc_graph_data helper in graph_store.py (correct and untouched)
  - phase: 10-graph-builder-worker
    provides: graph_rag_enabled gating pattern and worker safety net at line 119-121
provides:
  - delete_document_route wired to delete_doc_graph_data (gated, lenient)
  - reprocess_document wired to delete_doc_graph_data (gated, lenient)
  - 7 integration + unit tests proving the wiring (GRAPH-06, GRAPH-WORKER-03)
affects: [14-graph-status-api, 15-tech-debt-cleanup]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Gated graph cleanup at call site: if settings.graph_rag_enabled: try: await helper() except: log.error(event, kwargs)"
    - "Lenient error semantics for best-effort deletes: log graph_cleanup_failed and continue (matches blob/Qdrant delete patterns)"
    - "Graph cleanup ordering: graph first, then Qdrant chunks, then blobs, then MongoDB doc record (D-07/D-09)"

key-files:
  created:
    - tests/test_documents_graph_cleanup.py
  modified:
    - src/docingest/api/routes/documents.py

key-decisions:
  - "D-01/D-02: Gate at call site with if settings.graph_rag_enabled — NOT inside the helper (pure data layer stays pure)"
  - "D-03/D-04: Lenient error mode — graph cleanup failure logs graph_cleanup_failed with doc_id/tenant_id/error, then continues"
  - "D-07/D-09: Graph cleanup runs BEFORE Qdrant chunk delete in both routes"
  - "D-11: Sequential calls only — no asyncio.gather for graph+chunk deletes"
  - "D-12/D-13: graph_builder.py:119-121 safety net left untouched (defense-in-depth)"
  - "D-14/D-15: No community invalidation — communities remain batch artifacts"

patterns-established:
  - "Graph cleanup pattern: gated if settings.graph_rag_enabled: try: await delete_doc_graph_data(...) except Exception as e: log.error('graph_cleanup_failed', ...)"
  - "Test pattern: direct async route function invocation (no HTTP server), monkeypatch get_db/get_qdrant/delete_doc_chunks, structlog.testing.capture_logs for log assertions"

requirements-completed: [GRAPH-06, GRAPH-WORKER-03]

# Metrics
duration: 13min
completed: "2026-04-16"
---

# Phase 13 Plan 01: Wire Graph Data Lifecycle Cleanup Summary

**Synchronous graph entity/relationship cleanup wired into delete and reprocess routes via gated lenient call sites, closing FLOW-06 (orphaned entities on delete) and FLOW-04 (stale-data window on reprocess)**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-16T18:46:08Z
- **Completed:** 2026-04-16T18:59:00Z
- **Tasks:** 3 (Tasks 2 and 3 written atomically in one file creation)
- **Files modified:** 2

## Accomplishments

- Wired `delete_doc_graph_data` into `delete_document_route` — entities/relationships now cleaned up synchronously on document delete, before the route returns
- Wired `delete_doc_graph_data` into `reprocess_document` — stale graph data cleared before version bump and worker enqueue, preventing stale-data window
- Created 7-test file covering: happy path (both routes), gate-disabled path (both routes), shared-entity preservation, and lenient error path (both routes)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire delete_doc_graph_data into delete and reprocess routes** - `d0ee577` (feat)
2. **Tasks 2+3: Integration + lenient error tests** - `07d80f4` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/docingest/api/routes/documents.py` - Added `from docingest.config import settings` and `from docingest.db.graph_store import delete_doc_graph_data` imports; inserted gated lenient cleanup blocks in both `delete_document_route` and `reprocess_document`
- `tests/test_documents_graph_cleanup.py` - New file with 7 tests: 5 integration tests + 2 lenient error unit tests

## Files NOT Modified (defense-in-depth preserved)

- `src/docingest/db/graph_store.py` — helper is correct; pure data layer untouched (D-02)
- `src/docingest/workers/graph_builder.py` lines 119-121 — safety net preserved (D-12/D-13)

## Decisions Made

All decisions from 13-CONTEXT.md were honored:

- **D-01/D-02**: Gating at call site with `if settings.graph_rag_enabled:` — not pushed into helper
- **D-03/D-04**: Lenient mode — `except Exception as e: log.error("graph_cleanup_failed", doc_id=..., tenant_id=..., error=str(e))` — route still returns 200/202
- **D-05**: Matches existing blob/Qdrant error tolerance patterns (`contextlib.suppress`, bare `try/except: pass`)
- **D-06**: No retry, no metrics counter, no `graph_status='orphaned'` flag
- **D-07/D-08**: Delete route order: graph cleanup → Qdrant chunks → blobs → MongoDB record
- **D-09/D-10**: Reprocess route order: graph cleanup → Qdrant chunks → `increment_version` → `_enqueue_conversion`
- **D-11**: Sequential calls only (no `asyncio.gather` for graph+chunk deletes)
- **D-12/D-13**: Worker safety net at `graph_builder.py:119-121` left untouched
- **D-14/D-15**: No community invalidation; no `$pull` on `entity_ids[]`

## Deviations from Plan

### Minor: Tasks 2 and 3 written in single Write call

- **Found during**: Task 2 writing
- **Action**: Both the 5 integration tests (Task 2) and the 2 lenient error tests (Task 3) were written in a single `Write` tool call rather than Task 2 first + `Edit` append for Task 3
- **Impact**: Functionally identical result; single test file commit contains all 7 tests; all acceptance criteria for both tasks satisfied
- **All 7 tests pass; ruff clean**: Verified

No Rule 1/2/3/4 deviations.

## Issues Encountered

- `ruff` not globally installed; installed via `pip install ruff` (dev dependency)
- `pytest` not globally installed; installed via `pip install pytest pytest-asyncio`
- `docingest` package not installed in system Python; resolved via `pip install -e . --no-deps` to make the package importable without reinstalling all dependencies (spacy file lock prevented full install)
- One ruff E501 violation in test docstring (102 > 100 chars); suppressed with `# noqa: E501`

## User Setup Required

None - no external service configuration required. MongoDB must be running at `localhost:27017` (or `MONGODB_URI` env var) for integration tests to pass.

## Follow-up (Deferred)

- **Phase 14**: Surface `graph_status`, `entity_count`, `relationship_count` on `DocumentResponse` (INT-02 from audit)
- **Phase 15**: Remove duplicate `ensure_graph_indexes` call (INT-01); evaluate removing `graph_builder.py:119-121` safety net once route cleanup is proven in production

## Next Phase Readiness

- GRAPH-06 and GRAPH-WORKER-03 are satisfied — both routes clean up graph data synchronously
- FLOW-06 (orphaned entities on delete) closed
- FLOW-04 (stale-data window on reprocess) closed
- Phase 14 can proceed: `DocumentResponse` graph_status surface work has clean foundation

---
*Phase: 13-wire-graph-data-lifecycle-cleanup*
*Completed: 2026-04-16*
