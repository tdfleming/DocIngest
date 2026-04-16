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

**Phases:** 8-11 (7 plans)
**Requirements declared:** 25 (GRAPH-01..07, EE-01..08, GRAPH-WORKER-01..05, COMM-01..05)
**Status:** ⚠ Gap closure in flight (phases 12-15) — see `.planning/v1.0-MILESTONE-AUDIT.md`.

**Stats:**
- graph-worker: new ARQ worker with dedicated queue (`arq:queue:graph`)
- New services: `entity_extraction`, `community_detection`
- New models: Entity, Relationship, Community
- New dependencies: spaCy (`en_core_web_lg`), python-igraph, leidenalg, scikit-learn

**Git range:** `85e5a0e` (v1.0 ship) → `479736f` (gap closure phases added)

---
