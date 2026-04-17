# Phase 13: Wire Graph Data Lifecycle Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `13-CONTEXT.md` — this log preserves the alternatives considered.

**Session:** 2026-04-16
**Participants:** User (visionary), Claude (builder)

---

## Gray area selection

**Q:** Which gray areas should we discuss for Phase 13?

**Options presented:**
1. Error semantics — strict vs lenient failure mode
2. Call ordering — graph-first vs parallel vs sequential after
3. Worker safety net — keep vs remove `graph_builder.py:119-121`
4. Community invalidation — ignore vs auto-rebuild vs partial cleanup

**User selection:** ALL FOUR (multi-select).

---

## Area 1 — Error semantics

### Q1.1: Failure mode

**Options:**
- Strict — bubble as HTTP 500 (Recommended)
- Lenient — log and continue
- Strict on delete, lenient on reprocess

**User selection:** **Lenient — log and continue**

**Rationale (user's implicit):** Matches existing blob / Qdrant delete patterns in the same routes. Consistency > strict-ness for v1.0.

### Q1.2: Fail point / ordering of failure

**Options:**
- Graph first — fail fast (Recommended)
- Graph last — after other deletes
- Claude's discretion

**User selection:** **Claude's discretion**

**Rationale:** Compatible with lenient mode — ordering matters less when failures are swallowed. Planner will decide based on existing code style.

### Q1.3 (follow-up): Observability on silent failure

**Options:**
- Log error only (Recommended)
- Log + increment counter metric
- Log + set `graph_status='orphaned'`

**User selection:** **Log error only**

**Rationale:** No metrics infra available; `graph_status='orphaned'` doesn't apply to the delete case (doc is gone). structlog ERROR line is the right tolerance level.

### Q1.4 (follow-up): Continue or dig deeper?

**User selection:** **Move to call ordering**

---

## Area 2 — Call ordering

### Q2.1: Reprocess route ordering

**Options:**
- Clean graph → delete chunks → bump version → enqueue (Recommended)
- Delete chunks → clean graph → bump version → enqueue
- Parallel (asyncio.gather chunks + graph) → bump → enqueue

**User selection:** **Clean graph → delete chunks → bump version → enqueue**

**Rationale:** Full-cleanup-before-enqueue keeps reprocess atomic from caller's perspective; no stale-data window visible.

### Q2.2: Delete route ordering

**Options:**
- Graph → chunks → blobs → doc record (Recommended)
- Existing order + graph at the end (chunks → blobs → graph → doc)
- Parallel via asyncio.gather

**User selection:** **Graph → chunks → blobs → doc record**

**Rationale:** Outward-in order; doc record as the anchor deleted last.

### Q2.3 (follow-up): Concurrent in-flight `build_graph` job during reprocess

**Options:**
- Accept the race — worker's version check handles it (Recommended)
- Block reprocess if graph_status == 'building' (HTTP 409)
- Cancel in-flight ARQ job before enqueuing new one

**User selection:** **Accept the race — worker's version check handles it**

**Rationale:** `graph_builder.py:121` already cleans before building when version > 1. No concurrency primitives needed for v1.0.

### Q2.4 (follow-up): Continue or dig deeper?

**User selection:** **Move to worker safety net**

---

## Area 3 — Worker safety net

### Q3.1: Keep or remove `graph_builder.py:119-121`

**Options:**
- Keep as-is (Recommended)
- Remove it
- Keep + add "already cleaned by route" log

**User selection:** **Keep as-is**

**Rationale:** Defense-in-depth for non-route enqueue paths + race handling from Q2.3. Zero marginal cost.

### Q3.2 (follow-up): Continue or move on?

**User selection:** **Move to community invalidation**

---

## Area 4 — Community invalidation

### Q4.1: Handle communities referencing deleted entities?

**Options:**
- Ignore — stale until next rebuild (Recommended)
- Auto-mark communities as stale in document record
- Trigger async rebuild on every delete/reprocess
- Strip dead entity_ids from existing Community records

**User selection:** **Ignore — stale until next rebuild**

**Rationale:** Matches existing design (communities are batch artifacts, on-demand rebuild). Staying within phase scope — audit only flags FLOW-04/06 for entities/relationships, not communities.

### Q4.2 (follow-up): Create context or explore more?

**User selection:** **Create context**

---

## Summary of locked decisions (see 13-CONTEXT.md §decisions for full set)

| # | Decision |
|---|----------|
| D-01 | Gate at call site on `settings.graph_rag_enabled` |
| D-03 | Lenient error mode (log + continue) |
| D-06 | No retry, no metrics, no orphan flag |
| D-07 | Delete order: graph → chunks → blobs → doc |
| D-09 | Reprocess order: graph → chunks → version → enqueue |
| D-11 | No parallel `asyncio.gather` for cleanups |
| D-12 | Keep `graph_builder.py:119-121` safety net |
| D-13 | Accept race — worker handles it |
| D-14 | No community invalidation this phase |

## Deferred ideas captured

- Phase 14 will handle `DocumentResponse` fields (INT-02)
- Phase 15 will handle duplicate index call (INT-01) and consider removing the worker safety net
- Background orphan-sweep, metrics, admin cleanup API — all explicitly deferred
- Community auto-rebuild / stale-flag — explicitly rejected for v1.0

---

*Audit trail only. Decisions captured in 13-CONTEXT.md.*
