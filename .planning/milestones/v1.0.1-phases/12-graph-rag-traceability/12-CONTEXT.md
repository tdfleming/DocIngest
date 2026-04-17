# Phase 12: Restore Graph RAG Traceability - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning
**Source:** PRD Express Path (`.planning/v1.0-MILESTONE-AUDIT.md`)

<domain>
## Phase Boundary

**In scope:**
- Update `.planning/REQUIREMENTS.md` with full descriptions, definitions of done, and verification criteria for all 25 Graph RAG extension REQ-IDs (GRAPH-*, EE-*, GRAPH-WORKER-*, COMM-*).
- Update `.planning/PROJECT.md` to remove "Graph RAG / knowledge graph" from Out-of-Scope and add the shipped Graph RAG capabilities to Validated/Active sections.
- Update `.planning/MILESTONES.md` to capture the Graph RAG extension (phases 8-11) under the v1.0 milestone record.
- Add `requirements-completed` frontmatter to three SUMMARY files that are missing it:
  - `.planning/phases/10-graph-builder-worker/10-01-SUMMARY.md`
  - `.planning/phases/11-community-detection/11-01-SUMMARY.md`
  - `.planning/phases/11-community-detection/11-02-SUMMARY.md`
- Close the three REQ-IDs this phase owns: **GRAPH-WORKER-02**, **GRAPH-WORKER-05**, **COMM-05** (orphaned/frontmatter-only gaps; wiring already works per integration checker).

**Out of scope (explicitly NOT this phase):**
- Fixing functional gaps in code — handled by phases 13 (lifecycle cleanup), 14 (API surface), 15 (code quality).
- Producing `VERIFICATION.md` for phases 8-11 — that's `/gsd:verify-work` territory, not a planning phase.
- Producing `VALIDATION.md` for any phase — that's `/gsd:validate-phase`.
- Creating a new milestone (v1.1/v2.0) — the decision is to retroactively scope Graph RAG into v1.0.
- Touching any source code under `src/docingest/`. This is a pure-documentation phase.

</domain>

<decisions>
## Implementation Decisions

### PROJECT.md updates (locked)
- **Remove from Out of Scope:** The line `Graph RAG / knowledge graph — research-grade complexity for marginal gains`.
- **Add to Validated requirements section:** Graph RAG extension capabilities that are functionally wired (entity extraction, graph data models, graph builder worker, community detection rebuild API) — each marked as `v1.0 extension` to distinguish from the original MVP 23.
- **Update Context block:** Add a sentence noting that v1.0 was extended with Graph RAG (phases 8-11, 2026-04-12) after initial ship, and reference `.planning/v1.0-MILESTONE-AUDIT.md`.
- **Do NOT** add a Constraint or Key Decision row for Graph RAG — those are stable architecture facts that already live in `CLAUDE.md` and phase research docs.
- **Last updated** line should be bumped to `2026-04-16 after v1.0 gap closure planning`.

### MILESTONES.md updates (locked)
- Add a new block under the existing `v1.0 MVP (Shipped: 2026-03-04)` heading titled `### v1.0 Graph RAG Extension (2026-04-12)`.
- Include: phases 8-11 list, delivered capabilities (entity graph, knowledge graph storage, community detection), stats (4 phases, 7 plans, 25 REQ-IDs declared), and a cross-reference to `.planning/v1.0-MILESTONE-AUDIT.md`.
- Mark status as `⚠ Gap closure in flight (phases 12-15)` until phases 13-15 complete.
- Do NOT create a new top-level `## v1.1` or similar heading — Graph RAG is being scoped into v1.0 per audit recommendation.

### REQUIREMENTS.md expansion (locked — schema)
Every REQ-ID entry MUST include **all** of the following fields:
1. **Label** — short human name (already present).
2. **Description** — 1-2 sentence prose describing what the requirement delivers.
3. **Phase** — owning phase number (already present).
4. **Definition of Done (DoD)** — bulleted list of concrete conditions (code present, indexes created, API returns X, etc.).
5. **Verification criteria** — grep-able / test-runnable checks that a future `/gsd:verify-work` invocation can use (file path + symbol, test name, API call expected status, etc.).
6. **Status** — `Satisfied` / `Satisfied* (no VERIFICATION.md)` / `Partial — gap closure phase N` / `Pending — phase N` (existing).

### REQUIREMENTS.md status overrides (locked)
- **GRAPH-WORKER-02** — flip from `Pending — phase 12` to `Satisfied* (traceability added, VERIFICATION.md pending)`. Wiring is complete per integration checker; phase 12 only adds the traceability record.
- **GRAPH-WORKER-05** — same treatment: `Satisfied* (traceability added, VERIFICATION.md pending)`. Docker service + spaCy download are wired.
- **COMM-05** — same: `Satisfied* (traceability added, VERIFICATION.md pending)`. API route at `src/docingest/api/routes/graph.py` + mounted in `app.py` is working.
- All other REQ-IDs keep their existing status unchanged.

### SUMMARY frontmatter additions (locked — exact REQ-ID sets)
Derived from each SUMMARY's own "What shipped" section, cross-checked with phase PLAN's `requirements:` field and the audit's REQ-ID-to-phase map:

| SUMMARY file | `requirements-completed:` value |
|--------------|----------------------------------|
| `.planning/phases/10-graph-builder-worker/10-01-SUMMARY.md` | `[GRAPH-WORKER-01, GRAPH-WORKER-02, GRAPH-WORKER-03, GRAPH-WORKER-04, GRAPH-WORKER-05]` |
| `.planning/phases/11-community-detection/11-01-SUMMARY.md` | `[COMM-01, COMM-02, COMM-03, COMM-04]` |
| `.planning/phases/11-community-detection/11-02-SUMMARY.md` | `[COMM-05]` |

Rationale: even though some REQ-IDs are marked `partial` in the audit (the code works but has tech debt that phases 13-15 will close), the SUMMARY frontmatter reflects what was **delivered by that plan**, not the audit verdict. The traceability row (REQUIREMENTS.md Status field) is where audit-verdict nuance lives.

### Commit strategy (locked)
- One commit per artifact class, **in this order** to keep the graph of changes auditable:
  1. `docs(12): add traceability CONTEXT` — this file.
  2. `docs(12-01): expand REQUIREMENTS.md with full Graph RAG extension schema`
  3. `docs(12-02): update PROJECT.md to reflect shipped Graph RAG extension`
  4. `docs(12-03): update MILESTONES.md with v1.0 Graph RAG extension record`
  5. `docs(12-04): add requirements-completed frontmatter to 10-01, 11-01, 11-02 SUMMARYs`
  6. `docs(12-05): mark GRAPH-WORKER-02, GRAPH-WORKER-05, COMM-05 as satisfied in REQUIREMENTS.md` (can be folded into 12-01 if the planner prefers)
- Each commit must touch only the files named — no stray edits.

### Ordering constraints (locked)
- The REQUIREMENTS.md expansion (12-01) must land **before** the status overrides for GRAPH-WORKER-02/05, COMM-05 (12-05), or the status-overrides edit will conflict with an expanded schema.
- SUMMARY frontmatter edits (12-04) are independent and can run in parallel with the other tasks.
- PROJECT.md (12-02) and MILESTONES.md (12-03) are independent of everything else.

### Claude's Discretion
- Whether to split `docs(12-01)` and `docs(12-05)` into separate commits or one — planner's call based on task sizing. Default: one commit is fine because both edit the same file.
- Exact wording of the prose description / DoD / verification-criteria for each REQ-ID (must be grep-able and concrete, but the exact sentences are the planner/executor's to write).
- Internal ordering of REQ-IDs within REQUIREMENTS.md (currently grouped by phase — keep that grouping).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit (the PRD source)
- `.planning/v1.0-MILESTONE-AUDIT.md` — Full gap analysis; the frontmatter `gaps.*` blocks enumerate every REQ-ID this phase must address.

### Current-state planning artifacts (what to edit)
- `.planning/REQUIREMENTS.md` — Skeleton requirements file; phase 12 expands it.
- `.planning/ROADMAP.md` — Already updated with phases 12-15; do NOT change roadmap structure here.
- `.planning/PROJECT.md` — Still lists Graph RAG as Out-of-Scope; fix.
- `.planning/MILESTONES.md` — Only captures v1.0 MVP (phases 1-7); extend.

### SUMMARY files whose frontmatter must be updated
- `.planning/phases/10-graph-builder-worker/10-01-SUMMARY.md`
- `.planning/phases/11-community-detection/11-01-SUMMARY.md`
- `.planning/phases/11-community-detection/11-02-SUMMARY.md`

### Reference SUMMARY files (correct frontmatter shape)
- `.planning/phases/08-graph-data-models/08-01-SUMMARY.md` — has `requirements-completed: [GRAPH-01, ...]` (line ~33).
- `.planning/phases/08-graph-data-models/08-02-SUMMARY.md` — same pattern.
- `.planning/phases/09-entity-extraction/09-01-SUMMARY.md` — same pattern.

### Source-of-truth for each REQ-ID's wiring (for writing DoD + verification criteria)
- Graph data models: `src/docingest/models/graph.py`, `src/docingest/db/graph_store.py`, `src/docingest/db/mongodb.py::ensure_indexes` (graph index helper).
- Entity extraction: `src/docingest/services/entity_extraction.py`.
- Graph builder worker: `src/docingest/workers/graph_builder.py`, `src/docingest/db/qdrant.py::get_doc_chunks`, `docker/graph-worker.Dockerfile`.
- Community detection: `src/docingest/services/community_detection.py`, `src/docingest/api/routes/graph.py`, `src/docingest/api/app.py` (router mount).

### Phase PLANs (source of truth for declared REQ-IDs in `requirements:` frontmatter)
- `.planning/phases/08-graph-data-models/08-01-PLAN.md`, `08-02-PLAN.md`
- `.planning/phases/09-entity-extraction/09-01-PLAN.md`
- `.planning/phases/10-graph-builder-worker/PLAN.md` (aka 10-01)
- `.planning/phases/11-community-detection/11-01-PLAN.md`, `11-02-PLAN.md`

### Project conventions
- `CLAUDE.md` — project instructions (tech stack table, gating rules, logging conventions).

</canonical_refs>

<specifics>
## Specific Ideas

### REQ-ID coverage table (what Phase 12 must touch)

| REQ-ID | Owning phase | Audit status | Phase 12 action |
|--------|--------------|--------------|------------------|
| GRAPH-01..07 | 08 | Satisfied* / GRAPH-06 partial | Expand REQUIREMENTS.md entries (description, DoD, verification). Leave status untouched. |
| EE-01..08 | 09 | Satisfied* / EE-08 partial | Expand REQUIREMENTS.md entries. Leave status untouched. |
| GRAPH-WORKER-01..05 | 10 | Partial (01, 03, 04), Orphaned (02, 05) | Expand REQUIREMENTS.md entries. Flip 02, 05 to Satisfied*. Add `requirements-completed` to 10-01-SUMMARY.md. |
| COMM-01..05 | 11 | Partial (all) | Expand REQUIREMENTS.md entries. Flip 05 to Satisfied*. Add `requirements-completed` to 11-01 and 11-02 SUMMARYs. |

### Example REQ-ID entry shape (for planner reference)

```markdown
- [x] **GRAPH-WORKER-02** — Worker fetches chunks via `get_doc_chunks` — Phase: 10 — Status: Satisfied* (traceability added, VERIFICATION.md pending)
  - **Description:** The graph-worker must fetch a document's chunk texts from Qdrant (not MongoDB) to run entity extraction, because chunks live in the vector store. A dedicated `get_doc_chunks(tenant_id, doc_id)` helper wraps the Qdrant scroll RPC.
  - **Definition of Done:**
    - `get_doc_chunks` exported from `src/docingest/db/qdrant.py` and imported by `src/docingest/workers/graph_builder.py`.
    - Helper returns `list[ChunkRecord]` ordered by chunk index.
    - Tenant collection existence is respected (collection may not exist → return empty list).
  - **Verification criteria:**
    - `grep -n "def get_doc_chunks" src/docingest/db/qdrant.py` returns a match.
    - `grep -n "get_doc_chunks" src/docingest/workers/graph_builder.py` returns at least one call site.
    - Running the graph-worker against a tenant with existing chunks produces `entity_count > 0` on at least one document.
```

### Wording for PROJECT.md Validated section additions
Suggested new entries (planner may adjust wording):
- `✓ Graph RAG pipeline: entity extraction (spaCy NER + SVO relationships), knowledge graph storage (MongoDB entities/relationships), and community detection (multi-resolution Leiden + TF-IDF summaries) — v1.0 extension`
- `✓ Feature gating: \`GRAPH_RAG_ENABLED\` environment flag controls graph pipeline activation end-to-end (lifespan, chunker enqueue, worker, API) — v1.0 extension`

### MILESTONES.md block shape (for planner reference)

```markdown
### v1.0 Graph RAG Extension (2026-04-12)

**Delivered:** Knowledge-graph pipeline layered onto v1.0 MVP — spaCy-based entity/relationship extraction over chunked content, MongoDB graph store with tenant isolation, and on-demand Leiden community detection with TF-IDF summaries. All functionality gated by `GRAPH_RAG_ENABLED`.

**Phases:** 8-11 (7 plans)
**Requirements declared:** 25 (GRAPH-01..07, EE-01..08, GRAPH-WORKER-01..05, COMM-01..05)
**Status:** ⚠ Gap closure in flight (phases 12-15) — see `.planning/v1.0-MILESTONE-AUDIT.md`.

**Stats:**
- graph-worker: new ARQ worker with dedicated queue (`arq:queue:graph`)
- New services: `entity_extraction`, `community_detection`
- New models: Entity, Relationship, Community
- New dependencies: spaCy (`en_core_web_lg`), python-igraph, leidenalg, scikit-learn

**Git range:** `85e5a0e` (v1.0 ship) → `479736f` (gap closure phases added)
```

### Windows/shell note
All file edits in this phase must be done with the `Edit` and `Write` tools — no `sed -i`, no PowerShell `(Get-Content ...) -replace` one-liners. The codebase is cross-platform and the Python executor runs on Windows.

</specifics>

<deferred>
## Deferred Ideas

- **Creating VERIFICATION.md for phases 8-11** — this is the next natural step after phase 12, but is owned by `/gsd:verify-work` and would be its own phase or a run-per-phase command invocation.
- **Creating VALIDATION.md / Nyquist compliance** — owned by `/gsd:validate-phase`. The audit notes all 11 phases are Nyquist-missing; that's a separate cleanup.
- **Phase 08 tech debt (duplicate `ensure_graph_indexes` call)** — phase 15 closes this, not phase 12.
- **Retroactive split of Graph RAG into v1.1 / v2.0 milestones** — explicitly rejected by the audit recommendation. If reconsidered later, phase 12's REQUIREMENTS.md schema is compatible with either scoping decision.
- **PROJECT.md Key Decisions table entries for Graph RAG architecture choices** — nice-to-have, but those decisions are already documented in phase 08-11 research / summary docs; re-stating them in PROJECT.md is duplication.

</deferred>

---

*Phase: 12-graph-rag-traceability*
*Context gathered: 2026-04-16 via PRD Express Path (audit file)*
