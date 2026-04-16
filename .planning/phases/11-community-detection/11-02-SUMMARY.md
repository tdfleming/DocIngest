---
phase: 11-community-detection
plan: 02
subsystem: graph-rag
tags: [community-detection, api, tests, graph-rag]
dependency_graph:
  requires: [11-01]
  provides: [community-rebuild-api, community-detection-tests]
  affects: [api-routes, app-startup]
tech_stack:
  added: []
  patterns: [skipif-guards, graph-rag-gating]
key_files:
  created:
    - tests/test_community_detection.py
    - src/docingest/api/routes/graph.py
  modified:
    - src/docingest/api/app.py
decisions:
  - "All test classes guarded by needs_graph (igraph/leidenalg) since module-level imports prevent selective function import"
  - "Graph API returns 403 (not 404) when graph_rag_enabled is false, matching authorization semantics"
  - "Conditional ensure_graph_indexes in lifespan gated by settings.graph_rag_enabled"
metrics:
  duration: 3min
  completed: "2026-04-12"
  tasks: 2
  files: 3
requirements-completed: [COMM-05]
---

# Phase 11 Plan 02: Community Detection Tests & API Summary

Unit tests for community detection sync helpers plus POST /v1/graph/communities/rebuild endpoint with Tenant auth and graph_rag_enabled gating.

## What Was Built

### Task 1: Unit Tests (tests/test_community_detection.py)
13 unit tests covering all sync helper functions from community_detection.py:
- **TestExtractiveSummary** (4 tests): top sentence selection, empty input, short text fallback, exact count
- **TestGenerateCommunityTitle** (3 tests): top-3 by mention_count, single entity, determinism
- **TestBuildGraph** (4 tests): basic construction, edge deduplication with weight summing, nonexistent entity skip, vertex attributes
- **TestDetectCommunitiesMultiResolution** (2 tests): two-cluster detection at high resolution, low vs high resolution comparison

All tests use `pytest.mark.skipif` guards for optional dependencies (igraph, leidenalg, sklearn).

### Task 2: Graph API Route (src/docingest/api/routes/graph.py)
- `POST /v1/graph/communities/rebuild` endpoint
- Requires Tenant auth (API key with rate limiting)
- Gated by `settings.graph_rag_enabled` (returns 403 if disabled)
- Calls `build_communities(db, tenant_id)` and returns stats
- Structured logging for rebuild start/complete

### Task 2: App Mounting (src/docingest/api/app.py)
- Added graph router import and mounting under `/v1` prefix
- Added conditional `ensure_graph_indexes(db)` in lifespan when `graph_rag_enabled` is true
- Added `settings` import for the gating check

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | ee57f37 | test(11-02): add unit tests for community detection helpers |
| 2 | 9c34882 | feat(11-02): add graph API route and mount in app |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Module-level igraph import prevents selective function import**
- **Found during:** Task 1
- **Issue:** `_generate_community_title` is pure logic but lives in `community_detection.py` which imports igraph at module level, making all function imports fail without igraph installed
- **Fix:** Added `@needs_graph` skipif guard to `TestGenerateCommunityTitle` class (same as graph-dependent tests)
- **Files modified:** tests/test_community_detection.py

## Known Stubs

None -- all endpoints are fully wired to the community detection service.

## Verification

- 13 tests collected and pass (skipped in CI without optional deps)
- ruff check passes on all 3 files
- AST parse verification confirms `rebuild_communities` function exists
- `graph.router` confirmed mounted in app.py
