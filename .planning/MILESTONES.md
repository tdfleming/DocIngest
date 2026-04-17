# Project Milestones: DocIngest

## v1.0 MVP (Shipped: 2026-03-04)

**Delivered:** Multi-tenant document ingestion engine with full async pipeline, semantic search, API key auth, and structured observability — all running locally without cloud dependencies.

**Phases completed:** 1-7 (8 plans total)

**Key accomplishments:**
- Replaced all Azure cloud dependencies with local alternatives (MinIO for blob storage, FastEmbed for embeddings)
- Built document parsing pipeline supporting PDF, DOCX, HTML, TXT, and Markdown via Docling
- Implemented end-to-end async pipeline: upload → convert → chunk → embed → store with per-upload chunking config
- Added semantic vector search (Qdrant cosine) with document deletion and full vector cleanup
- Implemented API key auth with tenant-scoped isolation and Redis token-bucket rate limiting (fail-open)
- Added structured JSON logging with trace IDs and per-stage timing across the full pipeline

**Stats:**
- 28 files created/modified
- 2,118 lines of Python (source)
- 7 phases, 8 plans
- 2 days from start to ship (2026-03-03 → 2026-03-04)

**Git range:** `6e60969` → `85e5a0e`

**What's next:** TBD — next milestone discussion needed

### v1.0 Graph RAG Extension (2026-04-12)

**Delivered:** Knowledge-graph pipeline layered onto v1.0 MVP — spaCy-based entity/relationship extraction over chunked content, MongoDB graph store with tenant isolation, and on-demand Leiden community detection with TF-IDF summaries. All functionality gated by `GRAPH_RAG_ENABLED`.

**Phases:** 8-15 (12 plans)
**Requirements declared:** 25 (GRAPH-01..07, EE-01..08, GRAPH-WORKER-01..05, COMM-01..05)
**Status:** ✅ Shipped 2026-04-17 as v1.0.1 — all 25 REQ-IDs Satisfied, all audit gaps closed.

**Build phases (8-11):** Graph data models, entity extraction service, graph builder worker, community detection + API.
**Gap closure phases (12-15):**
- Phase 12 — Traceability (REQUIREMENTS.md, PROJECT.md, MILESTONES.md, SUMMARY frontmatter)
- Phase 13 — Wire synchronous graph cleanup into delete/reprocess routes (closed FLOW-04/FLOW-06)
- Phase 14 — Surface `graph_status`, `entity_count`, `relationship_count`, `graph_built_at` via DocumentResponse (closed INT-02)
- Phase 15 — Code quality & hardening: asyncio API migration, `idx_to_entity` robustness, `collection_exists` guard, INT-01 duplicate-call removal

**Stats:**
- graph-worker: new ARQ worker with dedicated queue (`arq:queue:graph`)
- New services: `entity_extraction`, `community_detection`
- New models: Entity, Relationship, Community
- New dependencies: spaCy (`en_core_web_lg`), python-igraph, leidenalg, scikit-learn
- Python LOC: 4,586 (up from 2,118 at v1.0 MVP)

**Git range:** `85e5a0e` (v1.0 ship) → v1.0.1 tag (today)
**Archives:** [milestones/v1.0.1-ROADMAP.md](milestones/v1.0.1-ROADMAP.md), [milestones/v1.0.1-REQUIREMENTS.md](milestones/v1.0.1-REQUIREMENTS.md)

---
