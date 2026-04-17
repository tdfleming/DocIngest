# Phase 15: Graph RAG Code Quality & Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `15-CONTEXT.md` — this log preserves the alternatives considered.

**Session:** 2026-04-17
**Participants:** User (visionary), Claude (builder)

---

## Pre-scout findings presented to user

Before the gray-area question, Claude surfaced 6 audit items and their code locations:

| Audit item | Location | State |
|---|---|---|
| EE-08 — `get_event_loop` | entity_extraction.py:217, 223 | Deprecated API |
| COMM-04 — `get_event_loop` | community_detection.py:52 | Deprecated API |
| COMM-01/02 — idx_to_entity fragility | community_detection.py:92 | `enumerate(entities)` |
| COMM-03 — missing collection guard | community_detection.py:326 | No exists-check |
| INT-01 — duplicate `ensure_graph_indexes` | mongodb.py:46 + app.py:33 | Double call |
| v1 carryover — configure_logging in workers | converter/graph_builder/chunker | Already present |

---

## Gray area selection

**Q:** Which gray areas should we discuss for Phase 15?

**Options:**
1. idx_to_entity fix approach
2. Collection-existence guard strategy
3. INT-01 — which call to remove
4. Test strategy + configure_logging audit

**User selection:** **"go with recommendations"** (via Other).

Interpretation: Lock in Claude's recommended option for each of the 4 areas without further questions. All decisions captured in CONTEXT.md §decisions.

---

## Locked recommendations

### Area 1 — asyncio migration (grouped with all 3 sites)
- Recommendation: One-line `get_event_loop()` → `get_running_loop()` swap at all 3 sites. Zero behavioral change. D-01, D-02, D-03.

### Area 2 — idx_to_entity fix
- Recommendation: Build `entity_id_to_entity` dict, look up via `graph.vs[m]["name"]` (vertex-name attribute = entity ID, set at _build_graph:224). Delete the old `idx_to_entity` dict comprehension. `_build_graph` signature stays unchanged. D-04 through D-09.

### Area 3 — Collection-existence guard
- Recommendation: New `collection_exists(client, tenant_id) -> bool` helper in `qdrant.py`, reusing the existing `_known_collections` cache. Call at top of `_fetch_chunk_texts`. Do NOT call `ensure_collection` (would create) or wrap in try/except (less explicit). D-10 through D-14.

### Area 4 — INT-01 duplicate
- Recommendation: Remove the call from `mongodb.py` (separation of concerns — low-level helper shouldn't know about graph). Keep the app.py lifespan call. Also remove the now-unused import in mongodb.py. D-15 through D-18.

### Area 5 — configure_logging (verification-only)
- Recommendation: No code changes needed — all 3 workers already have module-level calls. Add grep verification criterion only. D-19, D-20.

### Area 6 — Test strategy
- Recommendation: Mix. Unit tests for the behavioral refactors (idx_to_entity robustness, collection-exists guard). Grep-only verification for asyncio migration and INT-01 removal. Extend `tests/test_community_detection.py` — don't create a new test file. D-21 through D-25.

---

## Summary of locked decisions

| # | Decision |
|---|----------|
| D-01..03 | Migrate 3 `get_event_loop()` sites to `get_running_loop()` |
| D-04..09 | Replace `idx_to_entity` with id-keyed lookup via `graph.vs[m]["name"]` |
| D-10..14 | New `collection_exists` helper; no `ensure_collection` call, no try/except |
| D-15..18 | Remove graph-index call from mongodb.py; keep app.py lifespan |
| D-19..20 | configure_logging audit confirmed resolved; grep-only verification |
| D-21..25 | Extend test_community_detection.py with behavioral tests; grep-only for deprecation fixes |

## Deferred ideas captured

- Removing graph_builder.py:119-121 safety net — deferred again (phase 13's D-12/D-13 rationale still holds).
- Dataclass-ification of entities, swapping igraph/Leiden, metrics, VERIFICATION.md for phases 8-11 — all future-phase / separate workflow concerns.

---

*Audit trail only. Decisions captured in 15-CONTEXT.md.*
