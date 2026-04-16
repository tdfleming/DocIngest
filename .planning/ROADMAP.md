# Roadmap: DocIngest

**Current milestone:** v1.0 (gap closure in progress — see `.planning/v1.0-MILESTONE-AUDIT.md`)
**Last updated:** 2026-04-16

---

## Milestone v1.0 — MVP + Graph RAG Extension

**Status:** ⚠ Gap closure — 4 phases added on 2026-04-16 to close gaps identified by milestone audit.

### Original MVP (shipped 2026-03-04)

| Phase | Name | Status |
|-------|------|--------|
| 01 | Foundation & Infrastructure | ✅ shipped |
| 02 | Document Parsing | ✅ shipped |
| 03 | Chunking & Embedding | ✅ shipped |
| 04 | Search & Document Management | ✅ shipped |
| 05 | Auth & Multi-Tenancy | ✅ shipped |
| 06 | Reliability & Observability | ✅ shipped |
| 07 | Tech Debt Cleanup | ✅ shipped |

Full detail: [.planning/milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

### Graph RAG Extension (added after v1.0 ship, 2026-04-12)

| Phase | Name | Status |
|-------|------|--------|
| 08 | Graph Data Models | ✅ wired, ⚠ VERIFICATION.md missing |
| 09 | Entity Extraction | ✅ wired, ⚠ VERIFICATION.md missing |
| 10 | Graph Builder Worker | ✅ wired, ⚠ SUMMARY frontmatter + VERIFICATION.md missing |
| 11 | Community Detection | ✅ wired, ⚠ SUMMARY frontmatter + VERIFICATION.md missing |

### Gap Closure (added 2026-04-16)

#### Phase 12: Restore Graph RAG Traceability
**Goal:** Establish formal traceability for the Graph RAG extension (REQUIREMENTS.md, ROADMAP.md, PROJECT.md, MILESTONES.md, SUMMARY frontmatter).
**Requirements:** GRAPH-WORKER-02, GRAPH-WORKER-05, COMM-05 (orphaned/frontmatter) + planning-artifact gaps
**Gap Closure:** Structural pre-requisite for all other gap closure phases; closes planning-artifact gaps surfaced by audit.
**Plans:** 4/4 plans complete
- [x] 12-01-PLAN.md — Expand REQUIREMENTS.md with full 25-entry schema + flip GRAPH-WORKER-02/05 and COMM-05 to Satisfied*
- [x] 12-02-PLAN.md — Update PROJECT.md (remove Graph RAG from Out-of-Scope, add v1.0 extension entries, bump date)
- [x] 12-03-PLAN.md — Append v1.0 Graph RAG Extension block to MILESTONES.md
- [x] 12-04-PLAN.md — Add requirements-completed frontmatter to 10-01, 11-01, 11-02 SUMMARYs

#### Phase 13: Wire Graph Data Lifecycle Cleanup
**Goal:** Delete and reprocess document routes must synchronously clean up graph data before the graph-worker can re-enter.
**Requirements:** GRAPH-06, GRAPH-WORKER-03
**Gap Closure:** FLOW-06 (delete leaves orphaned graph data permanently), FLOW-04 (reprocess stale-data window).

#### Phase 14: Surface Graph Status via Document API
**Goal:** Graph processing fields written by the worker must be visible on `GET /v1/documents/{id}` and list responses.
**Requirements:** GRAPH-WORKER-01, GRAPH-WORKER-04
**Gap Closure:** INT-02 (`graph_status`, `entity_count`, `relationship_count` stripped by `_doc_to_response`).

#### Phase 15: Graph RAG Code Quality & Hardening
**Goal:** Close code-quality and fragility debt items identified in the audit.
**Requirements:** EE-08, COMM-01, COMM-02, COMM-03, COMM-04
**Gap Closure:** INT-01 (duplicate `ensure_graph_indexes`), asyncio deprecation, `idx_to_entity` fragility, missing `ensure_collection` guard, v1 carryover (`configure_logging()` in converter/graph_builder).

---

## Next Milestone

TBD — evaluate after v1.0 gap closure completes and re-audits clean.
