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
- ✓ Graph RAG pipeline: entity extraction (spaCy NER + SVO relationships), knowledge graph storage (MongoDB entities/relationships), and community detection (multi-resolution Leiden + TF-IDF summaries) — v1.0 extension
- ✓ Feature gating: `GRAPH_RAG_ENABLED` environment flag controls graph pipeline activation end-to-end (lifespan, chunker enqueue, worker, API) — v1.0 extension

### Active

(None yet — define requirements for next milestone)

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

Shipped v1.0 with 2,118 LOC Python.
Tech stack: FastAPI, ARQ (Redis job queue), Docling (doc conversion), FastEmbed (bge-small-en-v1.5, 384-dim), MongoDB (metadata), Qdrant (vectors), Redis (jobs + rate limiting), MinIO (blob storage).
All 23 v1 requirements shipped. No requirements adjusted or dropped.
Milestone audit passed with 100% scores across all categories.

Extended with Graph RAG pipeline post-ship (phases 8-11, 2026-04-12): entity/relationship extraction via spaCy, MongoDB graph store, Leiden community detection. See `.planning/v1.0-MILESTONE-AUDIT.md` for gap analysis.

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

---
*Last updated: 2026-04-16 after v1.0 gap closure planning*
