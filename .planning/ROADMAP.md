# Roadmap: DocIngest

## Overview

DocIngest goes from zero to a working multi-tenant document ingestion engine in 6 phases. We start by getting the local dev environment running (Docker Compose, no cloud deps), then build the pipeline layer by layer: parsing documents, chunking and embedding them, enabling search, layering on tenant-scoped auth, and finally hardening with proper error handling, status tracking, and observability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Foundation & Infrastructure** - Docker Compose runs all services locally with health checks
- [x] **Phase 2: Document Parsing** - Upload and convert PDF, DOCX, HTML, TXT, MD to processable text
- [ ] **Phase 3: Chunking & Embedding** - Split text into chunks, vectorize, orchestrate full async pipeline
- [ ] **Phase 4: Search & Document Management** - Semantic search and document deletion with vector cleanup
- [ ] **Phase 5: Auth & Multi-Tenancy** - API key auth with tenant-scoped, isolated operations
- [ ] **Phase 6: Reliability & Observability** - Status tracking, error reporting, structured logging

## Phase Details

### Phase 1: Foundation & Infrastructure
**Goal**: Local dev environment runs all services without cloud dependencies
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, PIPE-05
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts all services (API, MongoDB, Qdrant, Redis, MinIO)
  2. Health endpoint returns healthy status for all dependencies
  3. No Azure or cloud credentials required to run
**Research**: Unlikely (standard Docker Compose setup, well-documented services)
**Plans**: TBD

Plans:
- [ ] 01-01: TBD

### Phase 2: Document Parsing
**Goal**: Documents can be uploaded and converted to processable text
**Depends on**: Phase 1
**Requirements**: PARSE-01, PARSE-02, PARSE-03, PARSE-04, PIPE-04
**Success Criteria** (what must be TRUE):
  1. PDF file can be uploaded and converted to text via API
  2. DOCX file can be uploaded and converted to text via API
  3. HTML file can be uploaded and converted to text via API
  4. Plain text and Markdown files pass through without conversion
  5. Document metadata (filename, size, type, upload time) is stored in MongoDB
**Research**: Unlikely (Docling conversion is well-documented for supported formats)
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: Chunking & Embedding
**Goal**: Converted documents are chunked, vectorized, and stored end-to-end
**Depends on**: Phase 2
**Requirements**: CHUNK-01, CHUNK-02, CHUNK-03, PIPE-01
**Success Criteria** (what must be TRUE):
  1. Uploaded document is automatically converted, chunked, and embedded (full pipeline fires)
  2. Chunks are stored as vectors in Qdrant with correct dimensions (384)
  3. User can configure chunk_size, chunk_overlap, and strategy per upload
**Research**: Likely (Docling HybridChunker + FastEmbed alignment, tokenizer configuration)
**Research topics**: HybridChunker `max_tokens` parameter with bge-small-en-v1.5 tokenizer, optimal chunk size for 384-dim embeddings, FastEmbed batch embedding patterns
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: Search & Document Management
**Goal**: Users can search documents and manage stored content
**Depends on**: Phase 3
**Requirements**: SRCH-01, SRCH-02, PIPE-07
**Success Criteria** (what must be TRUE):
  1. User can search documents by semantic similarity and get ranked results
  2. Search results include chunk content and associated document metadata
  3. User can delete a document and all its vectors are removed from Qdrant
**Research**: Unlikely (standard Qdrant cosine search patterns, well-documented API)
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Auth & Multi-Tenancy
**Goal**: Secure tenant-isolated access to all operations
**Depends on**: Phase 4
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):
  1. API requires valid API key in request header
  2. Each API key is scoped to a tenant — operations only affect that tenant's data
  3. Tenant A cannot see or search Tenant B's documents
  4. Rate limiting enforces per-key limits with X-RateLimit headers
**Research**: Unlikely (Qdrant payload filtering and API key patterns are well-documented)
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

### Phase 6: Reliability & Observability
**Goal**: Pipeline is robust with proper monitoring and error handling
**Depends on**: Phase 5
**Requirements**: PIPE-02, PIPE-03, PIPE-06, INFRA-03
**Success Criteria** (what must be TRUE):
  1. User can check processing status of any document (queued/processing/completed/failed)
  2. Failed processing returns error type, failure stage, and actionable message
  3. All pipeline stages emit structured JSON logs with trace ID and timing
  4. Structured logging is consistent across all services
**Research**: Unlikely (standard Python logging and error handling patterns)
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Infrastructure | 1/1 | Complete | 2026-03-03 |
| 2. Document Parsing | 1/1 | Complete | 2026-03-04 |
| 3. Chunking & Embedding | 1/1 | Complete | 2026-03-04 |
| 4. Search & Document Management | 0/TBD | Not started | - |
| 5. Auth & Multi-Tenancy | 0/TBD | Not started | - |
| 6. Reliability & Observability | 0/TBD | Not started | - |
