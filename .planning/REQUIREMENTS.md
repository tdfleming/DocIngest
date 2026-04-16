# Requirements: DocIngest

**Current milestone:** v1.0 (gap closure)
**Last updated:** 2026-04-16

v1.0 MVP requirements (23 IDs, all satisfied) are archived at [.planning/milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md).

This file tracks the **Graph RAG extension** requirements that were declared in phase plan frontmatter but never centralized. Phase 12 will expand and formalize this file (full descriptions, definitions of done, etc.).

---

## Coverage

- **Total REQ-IDs:** 25
- **Satisfied:** 14
- **Partial (gap closure in flight):** 7
- **Orphaned (traceability only):** 4

---

## Graph Data Models (Phase 08)

- [x] **GRAPH-01** — Entity, Relationship, Community Pydantic models — Phase: 08-01 — Status: Satisfied*
- [x] **GRAPH-02** — `EntityType` enum + core entity fields — Phase: 08-01 — Status: Satisfied*
- [x] **GRAPH-03** — Relationship model with relation_type taxonomy — Phase: 08-01 — Status: Satisfied*
- [x] **GRAPH-04** — `graph_store.py` CRUD: upsert/get entities and relationships — Phase: 08-02 — Status: Satisfied*
- [x] **GRAPH-05** — Unique compound indexes for entity/relationship dedup — Phase: 08-02 — Status: Satisfied*
- [ ] **GRAPH-06** — Graph data cleanup on document delete — Phase: **13** (gap closure) — Status: Pending
- [x] **GRAPH-07** — `ensure_graph_indexes` helper — Phase: 08-01 — Status: Satisfied*

## Entity Extraction (Phase 09)

- [x] **EE-01** — spaCy `en_core_web_lg` lazy-loaded singleton — Phase: 09-01 — Status: Satisfied*
- [x] **EE-02** — Entity extraction per chunk with confidence filtering — Phase: 09-01 — Status: Satisfied*
- [x] **EE-03** — Fuzzy dedup of surface-form entities — Phase: 09-01 — Status: Satisfied*
- [x] **EE-04** — SVO-based relationship extraction — Phase: 09-01 — Status: Satisfied*
- [x] **EE-05** — `EntityType` mapping from spaCy labels — Phase: 09-01 — Status: Satisfied*
- [x] **EE-06** — Per-chunk limit (`MAX_ENTITIES_PER_CHUNK`) — Phase: 09-01 — Status: Satisfied*
- [x] **EE-07** — Configurable `ENTITY_CONFIDENCE_THRESHOLD` — Phase: 09-01 — Status: Satisfied*
- [ ] **EE-08** — Async wrappers for blocking spaCy calls — Phase: **15** (gap closure) — Status: Pending

## Graph Builder Worker (Phase 10)

- [ ] **GRAPH-WORKER-01** — Document `graph_status` tracked through build stages — Phase: **14** (gap closure) — Status: Pending
- [ ] **GRAPH-WORKER-02** — Worker fetches chunks via `get_doc_chunks` — Phase: **12** (traceability) — Status: Pending
- [ ] **GRAPH-WORKER-03** — Reprocess cleans up prior graph data synchronously — Phase: **13** (gap closure) — Status: Pending
- [ ] **GRAPH-WORKER-04** — Worker writes `entity_count` and `relationship_count` surfaced via API — Phase: **14** (gap closure) — Status: Pending
- [ ] **GRAPH-WORKER-05** — `graph-worker` Docker service + spaCy model download — Phase: **12** (traceability) — Status: Pending

## Community Detection (Phase 11)

- [ ] **COMM-01** — Leiden clustering over entity graph — Phase: **15** (gap closure) — Status: Pending
- [ ] **COMM-02** — Multi-resolution hierarchical community detection — Phase: **15** (gap closure) — Status: Pending
- [ ] **COMM-03** — TF-IDF extractive summaries per community — Phase: **15** (gap closure) — Status: Pending
- [ ] **COMM-04** — Community embedding via FastEmbed — Phase: **15** (gap closure) — Status: Pending
- [ ] **COMM-05** — `POST /v1/graph/communities/rebuild` API route — Phase: **12** (traceability) — Status: Pending

---

*`Satisfied*` reflects that implementation is wired and functionally correct per the audit's integration checker, but lacks formal VERIFICATION.md traceability. Promote to `Satisfied` after `/gsd:verify-work` produces VERIFICATION.md for each phase.

## Notes for Phase 12

Phase 12 should expand this file with:
- Full requirement descriptions (not just labels)
- Definitions of done per REQ-ID
- Verification criteria (what a VERIFICATION.md would check)

Source of truth for the declared REQ-IDs: the `requirements:` frontmatter in each phase plan under `.planning/phases/08-*` through `11-*`.
