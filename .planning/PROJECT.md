# DocIngest

## What This Is

A multi-tenant document ingestion engine that converts documents (PDF, HTML, DOCX, TXT, Markdown) into semantically chunked, vectorized content for RAG and search use cases. Built as a containerized pipeline with FastAPI, MongoDB, Qdrant, Redis, MinIO, and ARQ background workers. Runs fully locally via Docker Compose with no cloud dependencies.

## Core Value

Documents go in, searchable vectorized chunks come out — reliably and tenant-isolated.

## Requirements

### Validated

- ✓ Local development environment runs without Azure dependencies — v1.0
- ✓ Docker Compose brings up all services (API, workers, MongoDB, Qdrant, Redis, MinIO) — v1.0
- ✓ API starts and health endpoint returns healthy — v1.0
- ✓ End-to-end pipeline works: upload → convert → chunk → embed → search — v1.0
- ✓ API key auth works for tenant-scoped operations — v1.0
- ✓ Document parsing: PDF, DOCX, HTML via Docling; TXT/MD pass-through — v1.0
- ✓ Per-upload chunking configuration (chunk_size, chunk_overlap, strategy) — v1.0
- ✓ Semantic vector search with ranked results and document metadata — v1.0
- ✓ Document deletion with full vector cleanup — v1.0
- ✓ Per-key rate limiting with X-RateLimit headers (fail-open) — v1.0
- ✓ Processing status tracking (queued/processing/completed/failed) — v1.0
- ✓ Error classification with error_type, error_stage, and actionable messages — v1.0
- ✓ Structured JSON logging with trace IDs and per-stage timing — v1.0
- ✓ Graph RAG pipeline: entity extraction (spaCy NER + SVO relationships), knowledge graph storage (MongoDB entities/relationships), and community detection (multi-resolution Leiden + TF-IDF summaries) — v1.0.1
- ✓ Feature gating: `GRAPH_RAG_ENABLED` environment flag controls graph pipeline activation end-to-end (lifespan, chunker enqueue, worker, API) — v1.0.1
- ✓ Synchronous graph cleanup on document delete and reprocess (no orphaned entities/relationships) — v1.0.1
- ✓ Graph build progress surfaced via API: `graph_status`, `entity_count`, `relationship_count`, `graph_built_at` on `GET /v1/documents/{id}` and list responses — v1.0.1

### Active

(None yet — define requirements for next milestone via `/gsd:new-milestone`)

### Out of Scope

- Azure cloud deployment — local/Docker only for now
- Docker Swarm orchestration — Compose is sufficient for dev
- Folder watcher service — nice-to-have, not needed to validate core pipeline
- LLM answer generation — different product domain, return chunks for BYOLLM
- Custom embedding model hosting — GPU complexity, support configurable endpoints instead
- Real-time document sync (Drive, SharePoint) — OAuth complexity per connector
- OCR for scanned PDFs — accuracy/performance concerns, defer to v2+
- Fine-grained RBAC per document — tenant-level isolation sufficient for v1

## Context

### Current state (post v1.0.1, 2026-04-17)

Shipped **v1.0 MVP** (2026-03-04) and **v1.0.1 Graph RAG Extension** (2026-04-17).
Python LOC: 4,586 (src/) — up from 2,118 at v1.0.
Tech stack: FastAPI, ARQ (Redis job queue), Docling (doc conversion), FastEmbed (bge-small-en-v1.5, 384-dim), MongoDB (metadata + graph), Qdrant (vectors), Redis (jobs + rate limiting), MinIO (blob storage), spaCy (en_core_web_lg), python-igraph + leidenalg, scikit-learn (TF-IDF).

All 23 v1.0 MVP requirements validated. All 25 v1.0.1 Graph RAG REQ-IDs validated (build phases 8-11; gap closure phases 12-15). Every completion verified via VERIFICATION.md reports.

### Next milestone goals

Not yet scoped. Run `/gsd:new-milestone` to capture goals for the next release. Possible directions to consider during scoping:
- Frontend integration of graph fields (dashboard badge/column for `graph_status`, `entity_count`)
- OCR for scanned PDFs (previously out-of-scope)
- Real-time source connectors (Drive, SharePoint)
- Optional LLM answer generation or richer query/ranking
- Multi-language entity extraction beyond `en_core_web_lg`

<details>
<summary>Previous milestone notes (v1.0 MVP, 2026-03-04)</summary>

Shipped v1.0 with 2,118 LOC Python.
Tech stack: FastAPI, ARQ (Redis job queue), Docling (doc conversion), FastEmbed (bge-small-en-v1.5, 384-dim), MongoDB (metadata), Qdrant (vectors), Redis (jobs + rate limiting), MinIO (blob storage).
All 23 v1 requirements shipped. No requirements adjusted or dropped.
Milestone audit passed with 100% scores across all categories.

Extended with Graph RAG pipeline post-ship (phases 8-11, 2026-04-12): entity/relationship extraction via spaCy, MongoDB graph store, Leiden community detection. See `.planning/milestones/v1-MILESTONE-AUDIT.md` for gap analysis.

</details>

## Constraints

- **Cloud services**: No Azure accounts available — must use local alternatives (MinIO, FastEmbed)
- **Runtime**: Docker Compose for local development
- **Language**: Python 3.12+ (established by existing codebase)
- **Embeddings**: FastEmbed with bge-small-en-v1.5 (384-dim, local inference)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Replace Azure Blob with MinIO | No Azure resources available | ✓ Good — works seamlessly |
| Replace Azure OpenAI with FastEmbed | Local embedding model, no API keys needed | ✓ Good — 384-dim, ~30MB model |
| Single MinIO bucket with tenant path prefix | Simpler than per-tenant containers | ✓ Good — straightforward isolation |
| Embedding dimensions 1536 → 384 | bge-small-en-v1.5 native dimension | ✓ Good — sufficient for v1 |
| All blob/embedding functions sync | FastEmbed and MinIO clients are sync | ✓ Good — simpler than async wrappers |
| TXT/MD pass-through (no Docling) | Plain text doesn't need conversion | ✓ Good — faster processing |
| Rate limiter separate Redis connection | Avoid coupling with ARQ job queue | ✓ Good — independent lifecycle |
| Rate limiter fails open | Redis failure shouldn't block API | ✓ Good — availability over strictness |
| Error classification plain strings | Flexible, convention-based | ✓ Good — easy to extend |
| structlog contextvars for trace_id | Propagates across request and worker boundaries | ✓ Good — zero-arg logging |
| Per-stage timing via time.monotonic() | Accurate elapsed measurement | ✓ Good — not affected by clock drift |
| Lambda for Pydantic default_factory | datetime.now(UTC) needs argument unlike utcnow | ✓ Good — clean pattern |
| Pydantic v2 + StrEnum for graph models | Match document.py pattern for consistency | ✓ Good — v1.0.1 |
| `GRAPH_RAG_ENABLED` master switch, gated at call sites | MVP must remain operable without graph features | ✓ Good — v1.0.1 |
| spaCy lazy-load singleton with threading.Lock | Mirror embedding.py pattern; ~500MB loads once per process | ✓ Good — v1.0.1 |
| CPMVertexPartition for Leiden (not Modularity) | Per-level resolution control for hierarchical communities | ✓ Good — v1.0.1 |
| Retroactively scope Graph RAG into v1.0 | Per audit recommendation; single coherent milestone | ✓ Good — v1.0.1 |
| Lenient error mode on route-level graph cleanup | Match blob/Qdrant delete semantics; worker is consistency backstop | ✓ Good — v1.0.1 |
| Always-exposed response fields (no conditional omit) | Simpler contract; defaults are None/0 when gate off | ✓ Good — v1.0.1 |
| Id-keyed lookup via `graph.vs[m]["name"]` | Robust against entity list reordering | ✓ Good — v1.0.1 |

---
*Last updated: 2026-04-17 after v1.0.1 Graph RAG Extension shipped*
