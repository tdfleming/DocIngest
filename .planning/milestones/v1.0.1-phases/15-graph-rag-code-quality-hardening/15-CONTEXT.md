# Phase 15: Graph RAG Code Quality & Hardening - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

**In scope — 5 tech-debt fixes from the v1.0 milestone audit:**

1. **EE-08** — Migrate `asyncio.get_event_loop()` → `asyncio.get_running_loop()` in `src/docingest/services/entity_extraction.py` (2 sites: lines 217, 223).
2. **COMM-04** — Migrate `asyncio.get_event_loop()` → `asyncio.get_running_loop()` in `src/docingest/services/community_detection.py` (1 site: line 52).
3. **COMM-01 / COMM-02 — idx_to_entity fragility** — Replace the `enumerate(entities)` lookup at `community_detection.py:92` with an id-keyed lookup that does NOT assume vertex-index equals list-index.
4. **COMM-03 — missing collection guard** — Add a `collection_exists` helper in `src/docingest/db/qdrant.py`, call it at the top of `_fetch_chunk_texts` in `community_detection.py:326`; return `[]` if the tenant collection is missing.
5. **INT-01 — duplicate `ensure_graph_indexes` call** — Remove the call from `src/docingest/db/mongodb.py::ensure_indexes` (lines 45-46). Keep the `app.py` lifespan call as the single source.

**Also in scope — 1 verification-only item:**

6. **v1 carryover — `configure_logging()` in workers** — Already present in all 3 workers (`converter.py:15`, `graph_builder.py:16`, `chunker.py:18`). Phase 15 adds a grep verification criterion to confirm and closes the audit line item with zero code changes.

**Out of scope (explicitly NOT this phase):**
- Any behavioral changes to entity extraction, community detection, or graph building — all fixes are **correctness-preserving** (refactors, API migrations, defensive guards).
- Adding VERIFICATION.md for the earlier Graph RAG phases (8-11) — that's `/gsd:verify-work` territory.
- Any test infrastructure changes — reuse existing pytest + asyncio_mode="auto" setup.
- Frontend, Docker, CI, deployment concerns.
- Adding metrics, tracing, alerting, or ops tooling.
- Removing the graph-worker safety net at `graph_builder.py:119-121` — explicitly deferred from phase 13.
- Converting `idx_to_entity` into a full dataclass/model (just make the existing dict stable).
- Swapping igraph for NetworkX, Leiden for Louvain, or FastEmbed for another embedder.
- Any REQ-ID not listed above.

</domain>

<decisions>
## Implementation Decisions

### 1. asyncio migration (EE-08, COMM-04) — locked
- **D-01:** Replace `loop = asyncio.get_event_loop()` with `loop = asyncio.get_running_loop()` at all 3 sites: `entity_extraction.py:217`, `entity_extraction.py:223`, `community_detection.py:52`.
- **D-02:** No additional changes to surrounding `run_in_executor` calls — just the one-line swap.
- **D-03:** Rationale: `get_event_loop()` is deprecated on Python 3.10+ and raises `RuntimeError` on 3.14+. These sites are all inside `async def` functions where `get_running_loop()` is guaranteed to work. Zero behavioral change.

### 2. idx_to_entity fix (COMM-01 / COMM-02) — locked
- **D-04:** Replace the `enumerate(entities)` lookup at `community_detection.py:92` with an id-keyed lookup driven by igraph's own vertex-name attribute.
- **D-05:** Build `entity_id_to_entity = {str(e["_id"]): e for e in entities}` BEFORE the community-processing loop.
- **D-06:** Replace `member_entities = [idx_to_entity[m] for m in members]` (line 107) with `member_entities = [entity_id_to_entity[graph.vs[m]["name"]] for m in members]`. This uses the entity IDs stored in `g.vs["name"]` at `_build_graph:224` — robust against any change in entity list ordering.
- **D-07:** Delete the `idx_to_entity` dict comprehension at lines 92-94 entirely. Replace with the `entity_id_to_entity` dict.
- **D-08:** `_build_graph` signature and return (`tuple[ig.Graph, dict[str, int]]`) stays UNCHANGED. Do NOT add a second returned dict — the fix is purely in the caller.
- **D-09:** Rationale: This removes the hidden invariant "list index equals vertex index". The vertex-name attribute is already the canonical identifier and is preserved by igraph across all operations.

### 3. Collection guard (COMM-03) — locked
- **D-10:** Add a new async helper `collection_exists(client, tenant_id) -> bool` to `src/docingest/db/qdrant.py`. Place it near `ensure_collection` (line ~46) for discoverability.
- **D-11:** Implementation pattern (approximate):
  ```python
  async def collection_exists(client: AsyncQdrantClient, tenant_id: str) -> bool:
      name = _collection_name(tenant_id)
      if name in _known_collections:
          return True
      collections = await client.get_collections()
      existing = {c.name for c in collections.collections}
      _known_collections.update(existing)
      return name in existing
  ```
  Reuses the existing `_known_collections` cache (declared at `qdrant.py:42`) for zero-RPC fast path.
- **D-12:** In `_fetch_chunk_texts` (`community_detection.py:326`), after the existing `if not chunk_ids: return []` guard, add:
  ```python
  client = await get_qdrant()
  if not await collection_exists(client, tenant_id):
      return []
  ```
- **D-13:** Do NOT call `ensure_collection()` — that creates the collection, which is the wrong side effect for a read helper.
- **D-14:** Do NOT wrap the scroll in try/except — the guard at the top is explicit and cheaper than catching `UnexpectedResponse`.

### 4. INT-01 duplicate call — locked
- **D-15:** Remove the `if settings.graph_rag_enabled: await _ensure_graph_indexes(db)` block at `mongodb.py:45-46`.
- **D-16:** Also remove the now-unused import at `mongodb.py:8`: `from docingest.db.graph_store import ensure_graph_indexes as _ensure_graph_indexes`.
- **D-17:** Keep the call at `app.py:31-33` — the lifespan is the correct composition-layer home for feature-gated setup.
- **D-18:** Rationale: Separation of concerns — `mongodb.py::ensure_indexes` is a low-level helper for core document/log indexes; graph-specific setup belongs in the application composition layer (`app.py`) where the feature flag decision is already being made.

### 5. configure_logging (audit carryover) — locked
- **D-19:** No code changes. All 3 workers already call `configure_logging()` at module level:
  - `src/docingest/workers/converter.py:15`
  - `src/docingest/workers/graph_builder.py:16`
  - `src/docingest/workers/chunker.py:18`
- **D-20:** Add a single grep-based verification criterion to REQUIREMENTS.md (or the phase 15 VERIFICATION.md) confirming these lines exist. No new REQ-ID needed — this was audit-flagged as "should be confirmed" (audit line 149), not as a pending REQ-ID.

### 6. Test strategy — locked
- **D-21:** Unit tests for behavioral refactors (idx_to_entity fix, collection-exists guard). Test file: `tests/test_community_detection.py` — extend the existing file (already present per `ls tests/`), do not create a new one.
- **D-22:** Tests for the idx_to_entity fix should include a scenario where list order is deliberately scrambled relative to what a naive `enumerate` would produce — the canonical way to prove the fix is robust is to exercise it with non-trivial ordering.
- **D-23:** Tests for the collection-exists guard: one test with the tenant collection deleted → assert `_fetch_chunk_texts` returns `[]` without raising; one test with the collection present but empty chunk_ids.
- **D-24:** No new tests for the asyncio migration or INT-01 removal — these are grep-verifiable with zero behavior change. Existing tests must continue to pass (regression gate).
- **D-25:** No new tests for `configure_logging` confirmation — grep-only verification.

### Claude's Discretion
- Exact names of new test functions (e.g. `test_build_communities_handles_scrambled_entity_order` — planner's call).
- Whether to cache the `collections.collections` set longer than 1 call (already cached via `_known_collections`; no extra caching needed).
- Whether to combine the EE-08 + COMM-04 asyncio fixes into one commit or two (they touch 2 different files; one commit per file is fine, or a single "chore(15): migrate asyncio deprecated API" commit).
- Plan decomposition: single plan with 6 tasks, or 2-3 plans grouped by domain (asyncio / community-detection / mongodb). Planner's call based on wave/parallelism criteria — but all 5 REQ-IDs + 1 verification item MUST be covered.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit (PRD source)
- `.planning/v1.0-MILESTONE-AUDIT.md` lines 56-90 (EE-08, COMM-01, COMM-02, COMM-03, COMM-04 entries).
- `.planning/v1.0-MILESTONE-AUDIT.md` line 113 (INT-01 entry).
- `.planning/v1.0-MILESTONE-AUDIT.md` line 149 (v1 carryover `configure_logging`).

### Requirements
- `.planning/REQUIREMENTS.md` §EE-08 line 169.
- `.planning/REQUIREMENTS.md` §COMM-01 line 226.
- `.planning/REQUIREMENTS.md` §COMM-02 line 238.
- `.planning/REQUIREMENTS.md` §COMM-03 line 249.
- `.planning/REQUIREMENTS.md` §COMM-04 line 258.

### Source of truth — files to edit
- `src/docingest/services/entity_extraction.py` — 2 one-line replacements at lines 217, 223.
- `src/docingest/services/community_detection.py` — 1 one-line replacement at line 52; idx_to_entity refactor at lines 92-94 + 107; collection guard in `_fetch_chunk_texts` at line 326+.
- `src/docingest/db/qdrant.py` — add new `collection_exists` helper after existing `ensure_collection` at line 46.
- `src/docingest/db/mongodb.py` — remove lines 45-46 (graph-index call) and line 8 (import).
- `tests/test_community_detection.py` — extend with new test cases for idx_to_entity robustness and collection-exists guard.

### Source of truth — files to READ but NOT modify
- `src/docingest/api/app.py` lines 31-33 — the lifespan call stays.
- `src/docingest/workers/converter.py`, `graph_builder.py`, `chunker.py` — verify `configure_logging()` module-level calls; do not modify.
- `src/docingest/db/graph_store.py::ensure_graph_indexes` — helper is correct, used from app.py.

### Roadmap & planning
- `.planning/ROADMAP.md` §Phase 15 lines 61-64 — phase goal and gap-closure targets.
- `.planning/phases/12-graph-rag-traceability/12-CONTEXT.md` — shows REQUIREMENTS.md schema (Description, DoD, Verification criteria).
- `.planning/phases/13-wire-graph-data-lifecycle-cleanup/13-CONTEXT.md` — sibling tech-debt-ish phase; shows constraint-list / commit-message conventions.
- `.planning/phases/14-surface-graph-status-via-document-api/14-CONTEXT.md` — most recent completed sibling; shows how we test against live MongoDB.

### Project conventions
- `CLAUDE.md` — async patterns (`asyncio.get_running_loop()`), structlog, Edit-tool-only, pytest+asyncio_mode="auto".

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_known_collections: set[str]` at `qdrant.py:42` — in-memory cache, reuse for `collection_exists`.
- `_collection_lock: asyncio.Lock` at `qdrant.py:43` — not needed for read-only `collection_exists` (reads from set are safe without the lock).
- `_collection_name(tenant_id)` helper — use for consistent `tenant_{id}` naming.
- `graph.vs["name"]` — populated at `_build_graph:224` with entity IDs as strings; this is the robust lookup key for the idx_to_entity fix.
- `tests/test_community_detection.py` already exists — extend it, don't create a new test file.

### Established Patterns
- `async with _collection_lock:` pattern for Qdrant collection mutations (ensure_collection at `qdrant.py:50`). Not needed for read-only `collection_exists`, but don't mistakenly replicate it where unneeded.
- `loop = asyncio.get_running_loop()` — already used elsewhere in the codebase per CLAUDE.md; this is the target pattern.
- Test fixtures from `tests/test_community_detection.py` and `tests/test_documents_graph_cleanup.py` — real MongoDB + real Qdrant, not mocks.

### Integration Points
- `community_detection.py:52` (loop creation) and `:120` (`_fetch_chunk_texts` call) — both touched this phase.
- `community_detection.py:92-94` + `:107` — the idx_to_entity region.
- `qdrant.py:46` neighborhood — where the new helper lands, reusing the same cache.
- `mongodb.py:8, 45-46` — the INT-01 region; removing 3 lines total.

### Non-Integration (don't touch)
- `graph_builder.py` — not modified this phase (its safety net at 119-121 stays per phase 13 D-12/D-13).
- Frontend — no consumer.
- `graph_store.py` — helper is correct.
- Docker / infra / CI.

</code_context>

<specifics>
## Specific Ideas

### Approximate shape of the new qdrant.py helper
```python
async def collection_exists(client: AsyncQdrantClient, tenant_id: str) -> bool:
    """Return True if the tenant's Qdrant collection exists.

    Uses the module-level _known_collections cache to avoid redundant RPCs.
    """
    name = _collection_name(tenant_id)
    if name in _known_collections:
        return True
    collections = await client.get_collections()
    existing = {c.name for c in collections.collections}
    _known_collections.update(existing)
    return name in existing
```

### Approximate shape of the community_detection.py changes
```python
# Line 52 replacement:
loop = asyncio.get_running_loop()

# Lines 92-94 replacement (delete idx_to_entity; add entity_id_to_entity):
entity_id_to_entity: dict[str, dict[str, Any]] = {
    str(e["_id"]): e for e in entities
}

# Line 107 replacement:
member_entities = [
    entity_id_to_entity[graph.vs[m]["name"]] for m in members
]

# _fetch_chunk_texts — add guard after the "if not chunk_ids: return []" check at line 336:
client = await get_qdrant()
if not await collection_exists(client, tenant_id):
    return []
```

### Approximate shape of the entity_extraction.py changes
```python
# Lines 217 and 223 — same change at both sites:
loop = asyncio.get_running_loop()
```

### Approximate shape of the mongodb.py change
```diff
-from docingest.db.graph_store import ensure_graph_indexes as _ensure_graph_indexes
 ...
-    if settings.graph_rag_enabled:
-        await _ensure_graph_indexes(db)
```

### Verification criteria (for PLAN.md DoD)
- `grep -n "get_event_loop" src/docingest/services/entity_extraction.py` returns **0 matches**.
- `grep -n "get_event_loop" src/docingest/services/community_detection.py` returns **0 matches**.
- `grep -c "get_running_loop" src/docingest/services/entity_extraction.py` returns **2**.
- `grep -c "get_running_loop" src/docingest/services/community_detection.py` returns **1**.
- `grep -n "idx_to_entity" src/docingest/services/community_detection.py` returns **0 matches**.
- `grep -n "entity_id_to_entity" src/docingest/services/community_detection.py` returns **at least 2 matches** (definition + usage).
- `grep -n "def collection_exists" src/docingest/db/qdrant.py` returns **1 match**.
- `grep -n "await collection_exists" src/docingest/services/community_detection.py` returns **1 match** (inside `_fetch_chunk_texts`).
- `grep -n "_ensure_graph_indexes\|ensure_graph_indexes" src/docingest/db/mongodb.py` returns **0 matches**.
- `grep -c "configure_logging()" src/docingest/workers/converter.py src/docingest/workers/graph_builder.py src/docingest/workers/chunker.py` returns **3** (one per worker).
- New tests in `tests/test_community_detection.py` pass via `pytest tests/test_community_detection.py`.
- Full test suite (`pytest tests/` excluding pre-existing `test_entity_extraction.py` env gap) stays green.
- `ruff check src/` exits 0.

### Windows/shell note
All edits via Edit tool (no sed/awk). Hot-reload works for API; workers need `docker compose restart <worker>` to pick up changes if validating inside the running stack.

</specifics>

<deferred>
## Deferred Ideas

### Out of scope — separate concerns
- Removing the worker safety net at `graph_builder.py:119-121` — explicitly deferred from phase 13. Even though phase 13 wired synchronous cleanup on the route path, the safety net still covers non-route enqueues (manual ARQ pushes, direct DB edits) and the race from phase-13 D-13.
- Dataclass-ification of graph entities (replace dicts with typed models). Could be a future v1.1 or v2.0 hardening effort.
- Swapping igraph/leidenalg for alternatives. Architecture decision; locked for v1.0.
- Adding community count per document to DocumentResponse — not in scope (per phase 14 context).
- Running `/gsd:verify-work` to backfill VERIFICATION.md for phases 8-11. Separate workflow invocation, not a plan.
- Migration script for tenants whose `_known_collections` cache is stale — not needed (cache is process-local; restart invalidates).
- Prometheus metrics for cache hit/miss. Future ops phase.

### Out of scope — rejected/locked
- Creating a `CollectionsRegistry` class or singleton — the module-level `_known_collections` set is fine.
- Making `_build_graph` return 3-tuple `(graph, id_to_idx, idx_to_entity)` — explicitly rejected in D-08 (caller-side fix keeps `_build_graph` signature stable).
- Wrapping `_fetch_chunk_texts` in try/except on `UnexpectedResponse` — explicitly rejected in D-14 (guard at top is cleaner).
- Removing from app.py instead of mongodb.py — explicitly rejected in D-17/D-18 (separation of concerns keeps the feature-gate in the composition layer).

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 15-graph-rag-code-quality-hardening*
*Context gathered: 2026-04-17 — user said "go with recommendations"; all decisions locked to the recommended option for each area*
