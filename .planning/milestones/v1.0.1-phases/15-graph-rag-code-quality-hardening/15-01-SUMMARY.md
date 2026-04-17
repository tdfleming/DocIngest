---
phase: 15-graph-rag-code-quality-hardening
plan: "01"
subsystem: graph-rag
tags: [asyncio, community-detection, qdrant, mongodb, code-quality, tech-debt]
requirements_completed: [EE-08, COMM-01, COMM-02, COMM-03, COMM-04]
files_modified:
  created: []
  modified:
    - src/docingest/services/entity_extraction.py
    - src/docingest/services/community_detection.py
    - src/docingest/db/qdrant.py
    - src/docingest/db/mongodb.py
    - tests/test_community_detection.py
tasks_completed: 2
duration_minutes: 4
completed_date: "2026-04-17"
dependency_graph:
  requires: []
  provides:
    - asyncio.get_running_loop() at all async wrapper call sites in graph services
    - id-keyed entity lookup in community detection (entity_id_to_entity)
    - collection_exists() helper in qdrant.py with _known_collections cache
    - _fetch_chunk_texts returns [] gracefully when tenant collection missing
    - ensure_graph_indexes called only from app.py lifespan (INT-01 closed)
  affects:
    - src/docingest/services/community_detection.py (build_communities, _fetch_chunk_texts)
    - src/docingest/db/qdrant.py (new export: collection_exists)
    - src/docingest/db/mongodb.py (ensure_indexes no longer imports or calls graph_store)
tech_stack:
  added: []
  patterns:
    - asyncio.get_running_loop() for async wrapper pattern
    - id-keyed dict lookup via igraph vertex names for robust entity resolution
    - collection_exists() using module-level cache for zero-RPC fast path
key_files:
  created: []
  modified:
    - path: src/docingest/services/entity_extraction.py
      change: get_event_loop -> get_running_loop at 2 sites (lines 217, 223)
    - path: src/docingest/services/community_detection.py
      change: get_event_loop -> get_running_loop at line 52; idx_to_entity replaced with entity_id_to_entity; collection_exists guard added to _fetch_chunk_texts
    - path: src/docingest/db/qdrant.py
      change: new collection_exists() async helper added at line 46, reusing _known_collections cache
    - path: src/docingest/db/mongodb.py
      change: removed graph_store import (line 8) and duplicate ensure_graph_indexes call (lines 45-46)
    - path: tests/test_community_detection.py
      change: extended with TestEntityIdToEntityRobustness (2 tests) and TestFetchChunkTextsGuard (3 tests)
decisions:
  - "D-01/02/03: get_event_loop -> get_running_loop at all 3 sites (entity_extraction.py x2, community_detection.py x1). No other changes to run_in_executor calls."
  - "D-04/05/06/07: idx_to_entity comprehension deleted; entity_id_to_entity = {str(e['_id']): e for e in entities} built before loop; member lookup uses graph.vs[m]['name']."
  - "D-08: _build_graph signature unchanged (tuple[ig.Graph, dict[str, int]]). Fix is purely in caller."
  - "D-10/11: collection_exists() placed near ensure_collection at line 46, reusing _known_collections without lock (read-only)."
  - "D-12/13/14: collection guard added after 'if not chunk_ids: return []'; no ensure_collection() call; no try/except on scroll."
  - "D-15/16: mongodb.py import at line 8 removed; graph_rag block at lines 45-46 removed."
  - "D-17/18: app.py lifespan call at lines 30-33 left unchanged as sole source of ensure_graph_indexes."
  - "D-19/20: configure_logging() confirmed in all 3 workers (converter:15, graph_builder:16, chunker:18) via grep. No code changes."
  - "D-21/22/23: Tests extend existing test_community_detection.py; idx_to_entity test uses reversed entity list; collection-exists tests cover missing collection and empty chunk_ids."
  - "D-24/25: No new tests for asyncio migration, INT-01, or configure_logging. Grep-only verification."
---

# Phase 15 Plan 01: Graph RAG Code Quality Hardening Summary

**One-liner:** Closed 5 code-quality debt items — asyncio deprecated API migration (3 sites), robust id-keyed entity lookup replacing fragile enumerate-based indexing, defensive collection_exists guard for Qdrant, and duplicate graph-index initialization removal from mongodb.py.

## What Shipped

### Task 1: Production Code Fixes (all 5 items)

**EE-08 + COMM-04: asyncio.get_running_loop() migration**
- `entity_extraction.py` lines 217 and 223: `asyncio.get_event_loop()` → `asyncio.get_running_loop()`
- `community_detection.py` line 52: same swap
- These sites are inside `async def` functions where `get_running_loop()` is guaranteed. `get_event_loop()` is deprecated on Python 3.10+ and raises `RuntimeError` on 3.14+. Zero behavioral change.

**COMM-01 / COMM-02: idx_to_entity → entity_id_to_entity**
- Replaced `idx_to_entity: dict[int, dict[str, Any]] = {i: ent for i, ent in enumerate(entities)}` with `entity_id_to_entity: dict[str, dict[str, Any]] = {str(e["_id"]): e for e in entities}`
- Member entity lookup changed from `[idx_to_entity[m] for m in members]` to `[entity_id_to_entity[graph.vs[m]["name"]] for m in members]`
- The vertex `"name"` attribute is set to entity ID strings in `_build_graph` and is the canonical robust identifier. The old approach assumed list index equals vertex index — broken whenever entities are reordered.
- `_build_graph` signature unchanged per D-08.

**COMM-03: collection_exists guard**
- New `async def collection_exists(client, tenant_id) -> bool` added to `src/docingest/db/qdrant.py` after `_collection_lock` declaration
- Uses `_known_collections` cache for zero-RPC fast path; calls `client.get_collections()` only on cache miss
- `_fetch_chunk_texts` now calls `collection_exists` after the `if not chunk_ids: return []` guard — returns `[]` gracefully when tenant collection does not exist

**INT-01: duplicate ensure_graph_indexes removal**
- Removed `from docingest.db.graph_store import ensure_graph_indexes as _ensure_graph_indexes` (line 8) from `mongodb.py`
- Removed `if settings.graph_rag_enabled: await _ensure_graph_indexes(db)` block (lines 45-46) from `ensure_indexes` function
- `app.py` lifespan call at lines 30-33 remains the sole source. Separation of concerns restored.

**configure_logging verification (v1 audit carryover)**
- Confirmed via grep: `converter.py:15`, `graph_builder.py:16`, `chunker.py:18` all have module-level `configure_logging()` calls
- No code changes needed (D-19/D-20). Audit line item closed.

### Task 2: Test Extension

Extended `tests/test_community_detection.py` with 5 new test methods in 2 new classes:

**TestEntityIdToEntityRobustness (COMM-01/COMM-02):**
- `test_scrambled_entity_order_resolves_correctly` — builds graph in original order, creates entity_id_to_entity from reversed list, confirms all vertex lookups resolve to correct entity by ID
- `test_naive_enumerate_would_fail_with_scrambled_order` — demonstrates that old enumerate-based approach returns wrong entity for scrambled list while new id-keyed approach returns correct entity

**TestFetchChunkTextsGuard (COMM-03):**
- `test_returns_empty_when_collection_missing` — mocks get_qdrant + collection_exists=False, asserts [] returned and scroll never called
- `test_returns_empty_for_empty_chunk_ids` — calls _fetch_chunk_texts with [] and asserts [] returned (no mocking needed, short-circuits before I/O)
- `test_proceeds_when_collection_exists` — mocks collection_exists=True, asserts scroll called and text returned

## Files NOT Modified (DO NOT MODIFY constraints honored)

- `src/docingest/workers/graph_builder.py` — safety net at lines 119-121 preserved per phase 13 D-12/D-13
- `src/docingest/db/graph_store.py` — helper is correct, used from app.py
- `src/docingest/api/app.py` — lifespan is sole source of ensure_graph_indexes; left unchanged
- `src/docingest/workers/converter.py` — configure_logging already correct
- `src/docingest/workers/chunker.py` — configure_logging already correct

## Requirements Closed

| REQ-ID | Status | Evidence |
|--------|--------|----------|
| EE-08 | Closable | `grep -c "get_running_loop" entity_extraction.py` = 2; `get_event_loop` count = 0 |
| COMM-01 | Closable | `idx_to_entity` count in community_detection.py = 0; `entity_id_to_entity` count = 2 |
| COMM-02 | Closable | Member lookup uses `graph.vs[m]["name"]` — robust against entity list reordering |
| COMM-03 | Closable | `collection_exists` exported from qdrant.py; `await collection_exists` in _fetch_chunk_texts |
| COMM-04 | Closable | `grep -c "get_running_loop" community_detection.py` = 1; `get_event_loop` count = 0 |

## Deviations from Plan

None — plan executed exactly as written. All 10 edits (D-01 through D-18) applied as specified. All 5 new tests implemented per D-21 through D-23. D-24/D-25 honored (no tests for asyncio migration, INT-01, or configure_logging).

## INFORMATIONAL NOTE: GRAPH-05 Verification Criterion

REQUIREMENTS.md §GRAPH-05 has a verification criterion of `grep -n 'ensure_graph_indexes' mongodb.py` returning at least 1 match. After the INT-01 fix applied in this plan, that grep will return 0 matches (the import and call were removed from `mongodb.py`).

**GRAPH-05's Definition of Done** (the function `ensure_graph_indexes` is callable and idempotent) remains fully satisfied — the function still exists in `db/graph_store.py` and is called from `app.py` lifespan. Only the mongodb.py duplicate call was removed.

Future audits should be aware that:
- The verification criterion in GRAPH-05 (`grep mongodb.py`) is now stale/superseded by the INT-01 fix
- The correct verification for GRAPH-05 is `grep -n 'ensure_graph_indexes' src/docingest/db/graph_store.py` (returns the function definition) and `grep -n 'ensure_graph_indexes' src/docingest/api/app.py` (returns the canonical caller)
- GRAPH-05 status in REQUIREMENTS.md remains `Satisfied*` and does NOT need to be changed

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 1a9bc31 | fix(15-01): apply all 5 production code quality fixes |
| Task 2 | 71cd319 | test(15-01): extend community detection tests for idx_to_entity robustness and collection guard |

## Self-Check: PASSED
