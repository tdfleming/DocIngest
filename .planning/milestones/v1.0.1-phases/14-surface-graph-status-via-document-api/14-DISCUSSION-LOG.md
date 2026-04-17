# Phase 14: Surface Graph Status via Document API - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `14-CONTEXT.md` — this log preserves the alternatives considered.

**Session:** 2026-04-16
**Participants:** User (visionary), Claude (builder)

---

## Gray area selection

**Q:** Which gray areas should we discuss for Phase 14?

**Options presented:**
1. Fields to expose — 3 vs 4 vs 5 fields
2. Gating behavior — always expose vs conditional omit
3. Response shape consistency — which endpoints
4. Model declaration gap — graph_built_at handling

**User selection:** ALL FOUR (multi-select).

---

## Area 1 — Fields to expose

### Q1.1: Which graph fields should DocumentResponse expose?

**Options:**
- All 4 — including graph_built_at (Recommended)
- Spec-literal 3 — no graph_built_at
- 5 fields — add derived graph_error

**User selection:** **All 4 — graph_status, entity_count, relationship_count, graph_built_at**

**Rationale:** Worker already writes all 4; exposing only 3 leaves graph_built_at as dead Mongo data. UX wins from timestamp.

### Q1.2: Defaults for non-graph-built docs

**Options:**
- graph_status=None, counts=0, timestamp=None (Recommended)
- All fields required (no Optional)
- Omit fields entirely (`exclude_none`)

**User selection:** **graph_status=None, counts=0, timestamp=None**

**Rationale:** Matches Document model defaults; clients distinguish 'not built' (None) vs 'built-with-0-entities' (status='complete', counts=0).

---

## Area 2 — Gating behavior

### Q2.1: Behavior when graph_rag_enabled=false

**Options:**
- Always expose, show defaults (Recommended)
- Conditionally omit when gate is off
- Same as #1 but with explicit docstring

**User selection:** **Always expose, show defaults**

**Rationale:** Same response shape regardless of gate state. No FastAPI exclude logic. Simpler contract. REQ language interpreted as "values of interest when gate is on" not "conditional field existence".

### Q2.2: Gate ON but worker hasn't run yet

**Options:**
- Same as gate-off defaults (Recommended)
- graph_status='pending' placeholder

**User selection:** **Same as gate-off defaults**

**Rationale:** No synthesized placeholders. `None`/`complete` distinction is sufficient.

---

## Area 3 — Response shape consistency

### Q3.1: Which endpoints get the fields?

**Options:**
- Detail + list only (Recommended)
- All 5 response types
- Detail only (skip list)

**User selection:** **Detail + list only**

**Rationale:** Both funnel through single helper `_doc_to_response`. Upload/reprocess/delete return operational dicts (different contract) — leave them alone.

### Q3.2: Continue or dig deeper?

**User selection:** **Move to model declaration**

---

## Area 4 — Model declaration gap

### Q4.1: graph_built_at handling in model layer

**Options:**
- Add to Document model + DocumentResponse (Recommended)
- Read from dict directly
- Defer to Phase 15

**User selection:** **Add to Document model + DocumentResponse**

**Rationale:** Type safety + OpenAPI cleanliness. Worker write path already correct (extra_fields); just cosmetic/contract-level fix. Planner serializes via `.isoformat() if doc.get(...) else None` pattern (same as created_at/updated_at).

### Q4.2: Create context or explore more?

**User selection:** **Create context**

---

## Summary of locked decisions (see 14-CONTEXT.md §decisions for full set)

| # | Decision |
|---|----------|
| D-01 | Expose all 4 fields (graph_status, entity_count, relationship_count, graph_built_at) |
| D-02 | Type/defaults mirror Document model; graph_built_at as ISO string |
| D-03 | Null/zero defaults for pre-build docs (no placeholder statuses) |
| D-05 | Always expose — no conditional omit based on gate state |
| D-07 | Only `DocumentResponse` + `_doc_to_response` change (affects 2 endpoints) |
| D-08 | Operational routes (upload/reprocess/delete/batch) unchanged |
| D-09 | Add `graph_built_at` to Document model |
| D-10 | Worker write path untouched |
| D-11 | `.isoformat() if ... else None` pattern for datetime serialization |

## Deferred ideas captured

- Phase 15 will handle INT-01 (duplicate ensure_graph_indexes), EE-08 (asyncio deprecation), and optionally remove the worker safety net
- No frontend work in scope — future phase
- No community_count exposure (not in phase 14 REQ-IDs)
- No `graph_error` derived field (explicitly rejected)
- No backfill migration (Pydantic defaults + `.get()` handle missing keys)

---

*Audit trail only. Decisions captured in 14-CONTEXT.md.*
