# DocIngest

## What This Is

A multi-tenant document ingestion engine that converts documents (PDF, HTML, DOCX) into semantically chunked, vectorized content for RAG and search use cases. Built as a containerized pipeline with FastAPI, MongoDB, Qdrant, Redis, and background workers. Originally built in a previous Claude Code session, now being picked up to get running and extend.

## Core Value

Documents go in, searchable vectorized chunks come out — reliably and tenant-isolated.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Local development environment runs without Azure dependencies (mock Blob Storage, mock Azure OpenAI)
- [ ] Docker Compose brings up all services (API, workers, MongoDB, Qdrant, Redis)
- [ ] API starts and health endpoint returns healthy
- [ ] End-to-end pipeline works: upload document → convert → chunk → embed → search
- [ ] Test suite covering core functionality (API routes, conversion, chunking, embedding, search)
- [ ] API key auth works for tenant-scoped operations

### Out of Scope

- Azure cloud deployment — local/Docker only for now
- Docker Swarm orchestration — Compose is sufficient for dev
- Folder watcher service — nice-to-have, not needed to validate core pipeline
- Production hardening (rate limiting tuning, scaling) — premature until core works

## Context

- Codebase was generated in a previous Claude Code session based on DESIGN.md
- Python 3.12+ with FastAPI, ARQ (Redis job queue), Docling (doc conversion)
- Existing code structure: `src/docingest/` with api/, db/, models/, services/ modules
- Azure dependencies (Blob Storage, OpenAI embeddings) need local mock alternatives
- Design specifies: MongoDB for metadata, Qdrant for vectors, Redis for job queue
- Reranker provider is TBD in design — cross-encoder options listed but not decided

## Constraints

- **Cloud services**: No Azure accounts available — must mock Blob Storage and Azure OpenAI locally
- **Runtime**: Docker Compose for local development
- **Language**: Python 3.12+ (established by existing codebase)
- **Embeddings**: Need a local embedding model or mock to replace Azure OpenAI text-embedding-3-small

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Mock Azure services locally | No Azure resources available, need to run standalone | — Pending |
| Docker Compose over Swarm | Dev environment simplicity | — Pending |
| Skip folder watcher initially | Focus on core pipeline first | — Pending |

---
*Last updated: 2026-03-03 after initialization*
