# Phase 13: Wire Graph Data Lifecycle Cleanup - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

**In scope:**
- Add synchronous `delete_doc_graph_data(db, tenant_id, doc_id)` calls to:
  - `delete_document_route` in `src/docingest/api/routes/documents.py` (closes FLOW-06).
  - `reprocess_document` in `src/docingest/api/routes/documents.py` (closes FLOW-04).
- Both call sites gated on `settings.graph_rag_enabled` at the route level.
- Keep the graph-worker's existing self-cleanup at `graph_builder.py:119-121` as-is (defense-in-depth + race handler).
- Close REQ-IDs **GRAPH-06** and **GRAPH-WORKER-03**.

**Out of scope (explicitly NOT this phase):**
- Modifying `delete_doc_graph_data` itself — the helper is already correct (phase 08/10 work).
- Changing the graph-worker (keep its safety net intact).
- Community invalidation, cleanup, or auto-rebuild — communities stay stale-between-rebuilds per original design.
- Fixing Qdrant delete error handling, blob delete patterns, or any other non-graph lifecycle concern.
- API surface changes (`graph_status` / `entity_count` fields on `DocumentResponse`) — that's phase 14.
- Tech debt from the audit (duplicate `ensure_graph_indexes`, asyncio deprecation, etc.) — that's phase 15.
- Adding metrics/counters, admin cleanup scripts, or background orphan sweeps.
- Concurrency controls (409-on-in-flight-build, ARQ job cancellation) — the worker's version check is sufficient.

</domain>

<decisions>
## Implementation Decisions

### Gating (locked)
- **D-01:** Gate both new `delete_doc_graph_data` calls on `if settings.graph_rag_enabled:` at the route level. Matches the pattern established in phases 8-11 and in `graph_builder.py:47`.
- **D-02:** Do NOT push the gate into `delete_doc_graph_data` itself — the helper stays a pure data-layer function.

### Error semantics (locked)
- **D-03:** **Lenient mode** — if `delete_doc_graph_data` raises, swallow the exception and log at ERROR level with `structlog`. The document delete/reprocess request still succeeds (returns 200/202 as today).
- **D-04:** Log line MUST include `doc_id`, `tenant_id`, and the exception (`exc_info=True` or `error=str(e)` per existing codebase style). Event name: `graph_cleanup_failed`.
- **D-05:** Rationale: matches existing `delete_blob` / Qdrant delete patterns (both use `contextlib.suppress` or bare `try/except: pass`). A strict HTTP 500 on transient Mongo errors would be worse UX than the status quo for callers.
- **D-06:** No retry, no metrics counter, no `graph_status='orphaned'` flag. The worker's own cleanup at line 121 eventually reconciles on next reprocess, which is acceptable tolerance.

### Call ordering — delete route (locked)
- **D-07:** Order inside `delete_document_route`: **graph cleanup → Qdrant chunks → blobs (original + markdown) → MongoDB document record**.
- **D-08:** Graph cleanup goes FIRST (highest-level refs first, anchor record last). If graph cleanup fails in lenient mode, downstream deletes still proceed (matching status-quo behavior for blob/chunk failures).

### Call ordering — reprocess route (locked)
- **D-09:** Order inside `reprocess_document`: **graph cleanup → Qdrant chunks → `increment_version` → `_enqueue_conversion`**.
- **D-10:** Both cleanups (graph + chunks) MUST complete before version bump and enqueue, so the new pipeline starts from a clean slate.
- **D-11:** Do NOT parallelize graph + chunk deletes via `asyncio.gather` — sequential is easier to reason about, ~50ms savings not worth the concurrency complexity in a gap-closure phase.

### Worker safety net (locked)
- **D-12:** Leave `graph_builder.py:119-121` (`if version > 1 or graph_status is not None: await delete_doc_graph_data(...)`) UNTOUCHED. It acts as defense-in-depth against:
  - Any non-route path that enqueues graph builds (manual ARQ pushes, direct DB writes).
  - The race between a lingering previous `build_graph` job and a fresh enqueue (see D-13).
- **D-13:** Accept the race where a previous in-flight `build_graph` might complete after a reprocess route clears state — the worker's own line-121 cleanup handles it on the next run. No 409-blocking, no ARQ job cancellation, no in-flight status tracking.

### Community invalidation (explicitly deferred)
- **D-14:** Do NOT modify Community records when entities/relationships are deleted. Communities remain on-demand and may reference deleted entities until the next `POST /v1/graph/communities/rebuild`. This matches the existing design (communities are a batch artifact, not a live view).
- **D-15:** No `communities_stale` flag, no auto-rebuild, no `$pull` on `entity_ids[]`.

### Claude's Discretion
- Exact log line wording and any additional context fields (as long as event name is `graph_cleanup_failed` and doc_id/tenant_id are bound).
- Whether to add a comment block above each new call site explaining the lenient design choice (recommended: yes, short).
- Test file layout (new `tests/test_documents_graph_cleanup.py` vs. extending an existing test file).
- Import organisation in `documents.py` (where to add `from docingest.db.graph_store import delete_doc_graph_data`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit (PRD source)
- `.planning/v1.0-MILESTONE-AUDIT.md` §FLOW-04, §FLOW-06 (lines ~124-131, 267-268) — evidence and scope for both gap items.

### Requirements
- `.planning/REQUIREMENTS.md` §GRAPH-06 (line 78) — definition of done and verification criteria for delete-path cleanup.
- `.planning/REQUIREMENTS.md` §GRAPH-WORKER-03 (line 199) — definition of done and verification criteria for reprocess-path cleanup.

### Source of truth — files to edit
- `src/docingest/api/routes/documents.py` — two routes: `delete_document_route` (line 343), `reprocess_document` (line 369). **Only these two functions are modified.**

### Source of truth — helpers used (do NOT modify)
- `src/docingest/db/graph_store.py` line 387 — `delete_doc_graph_data` signature and semantics.
- `src/docingest/workers/graph_builder.py` lines 47, 119-121 — gating pattern + worker safety net (left untouched).
- `src/docingest/config.py` — `settings.graph_rag_enabled` flag.

### Roadmap & planning
- `.planning/ROADMAP.md` §Phase 13 (line 47-50) — phase goal and gap-closure targets.
- `.planning/phases/12-graph-rag-traceability/12-CONTEXT.md` — prior phase; confirms REQUIREMENTS.md schema and status semantics in use.

### Project conventions
- `CLAUDE.md` — gating rules (`graph_rag_enabled`), logging (`structlog`), async patterns, Edit/Write tools for cross-platform edits.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `delete_doc_graph_data(db, tenant_id, doc_id)` at `graph_store.py:387` — already correct, idempotent, handles orphan cleanup in two phases ($pull + delete-empty). Just needs to be called.
- `settings.graph_rag_enabled` — the gating flag, already used in 3 call sites (graph_builder, chunker, graph API route).
- `get_db()` from `docingest.db.mongodb` — already imported in both routes.

### Established Patterns
- Gating at call site with `if settings.graph_rag_enabled:` (not inside helpers).
- Lenient error handling for best-effort deletes — `contextlib.suppress(Exception)` around blob deletes, bare `try/except: pass` around Qdrant chunk delete in `reprocess_document`.
- `structlog.get_logger()` module-level, `log.info` / `log.error` with kwargs for structured context.
- Pure async routes; no thread-pool offload needed because `delete_doc_graph_data` is Motor-native async.

### Integration Points
- Line ~352 in `delete_document_route` (currently starts with Qdrant delete) — graph cleanup inserts BEFORE.
- Line ~377-381 in `reprocess_document` (currently `try: qdrant = ...; await delete_doc_chunks(...); except: pass`) — graph cleanup inserts BEFORE.
- Import block at top of `documents.py` — add `from docingest.db.graph_store import delete_doc_graph_data`.
- No API response schema change — both routes return the same shape as today.

</code_context>

<specifics>
## Specific Ideas

### Shape of the new calls

**Delete route** (approximate shape — exact wording is executor's call):
```python
async def delete_document_route(tenant: Tenant, doc_id: str):
    db = await get_db()
    doc = await get_document(db, doc_id, tenant["tenant_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Graph cleanup first (lenient — log and continue on failure)
    if settings.graph_rag_enabled:
        try:
            await delete_doc_graph_data(db, tenant["tenant_id"], doc_id)
        except Exception as e:
            log.error(
                "graph_cleanup_failed",
                doc_id=doc_id,
                tenant_id=tenant["tenant_id"],
                error=str(e),
            )

    # ... existing Qdrant, blob, doc deletes unchanged ...
```

**Reprocess route**:
```python
async def reprocess_document(request: Request, tenant: Tenant, doc_id: str):
    db = await get_db()
    doc = await get_document(db, doc_id, tenant["tenant_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Graph cleanup first (lenient — log and continue on failure)
    if settings.graph_rag_enabled:
        try:
            await delete_doc_graph_data(db, tenant["tenant_id"], doc_id)
        except Exception as e:
            log.error(
                "graph_cleanup_failed",
                doc_id=doc_id,
                tenant_id=tenant["tenant_id"],
                error=str(e),
            )

    # ... existing Qdrant chunk delete + version bump + enqueue unchanged ...
```

### Verification criteria (handed to planner for PLAN.md DoD)
- `grep -n 'delete_doc_graph_data' src/docingest/api/routes/documents.py` returns **at least 2** matches (one in delete, one in reprocess).
- `grep -n 'from docingest.db.graph_store import delete_doc_graph_data' src/docingest/api/routes/documents.py` returns 1 match.
- `grep -n 'graph_cleanup_failed' src/docingest/api/routes/documents.py` returns **at least 2** matches (both call sites log consistently).
- Integration test: seed 2 entities + 1 relationship for a doc_id → call DELETE /v1/documents/{id} with `GRAPH_RAG_ENABLED=true` → assert MongoDB `entities.count({doc_ids: doc_id}) == 0`.
- Integration test: same seeding → call POST /v1/documents/{id}/reprocess → assert entities removed synchronously (before worker runs).
- Unit test: mock `delete_doc_graph_data` to raise → assert route still returns 200/202 and logs `graph_cleanup_failed`.

### Windows/shell note
All edits via `Edit` tool — no `sed -i`, no PowerShell replace commands. The API already has hot-reload via `uvicorn --reload` in the ingestion-api Docker container, so post-commit verification is a simple container restart or reload trigger.

</specifics>

<deferred>
## Deferred Ideas

### Out of scope — belongs in Phase 14
- Surfacing `graph_status`, `entity_count`, `relationship_count` on `DocumentResponse` (INT-02 in audit). Noted for Phase 14.

### Out of scope — belongs in Phase 15
- Removing duplicate `ensure_graph_indexes` call (INT-01).
- Deleting the worker safety net at `graph_builder.py:119-121` once route cleanup is proven.

### Out of scope — separate ops concern
- Background orphan-sweep job for tenants that experienced lenient-mode failures.
- Prometheus-style metrics for `graph_cleanup_failed_total`.
- Admin API endpoint for manual graph cleanup.
- UI "communities stale" banner after deletes.

### Out of scope — design choice stays
- Strict (HTTP 500) error semantics — explicitly rejected in D-03. Worker's safety net + error log is the tolerance story.
- Community invalidation / `$pull` from `entity_ids[]` — explicitly rejected in D-14. Communities remain batch artifacts.
- Parallel cleanup via `asyncio.gather(graph, chunks)` — explicitly rejected in D-11.
- ARQ job cancellation / 409-on-in-flight — explicitly rejected in D-13.

### Reviewed Todos (not folded)
None — no pending todos matched this phase.

</deferred>

---

*Phase: 13-wire-graph-data-lifecycle-cleanup*
*Context gathered: 2026-04-16*
