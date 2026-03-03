# Requirements: DocIngest

**Defined:** 2026-03-03
**Core Value:** Documents go in, searchable vectorized chunks come out — reliably and tenant-isolated.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Document Parsing

- [ ] **PARSE-01**: System can convert PDF documents to processable text via Docling
- [ ] **PARSE-02**: System can convert DOCX documents to processable text via Docling
- [ ] **PARSE-03**: System can convert HTML documents to processable text
- [ ] **PARSE-04**: System can accept plain text and Markdown documents directly

### Chunking & Embedding

- [ ] **CHUNK-01**: System splits converted text into chunks using recursive fixed-size strategy (400-512 tokens, 10-20% overlap)
- [ ] **CHUNK-02**: System generates vector embeddings for each chunk using FastEmbed (bge-small-en-v1.5, 384-dim)
- [ ] **CHUNK-03**: User can configure chunk_size, chunk_overlap, and chunking strategy per upload via API parameters

### Pipeline & Processing

- [ ] **PIPE-01**: Upload triggers async pipeline: upload → convert → chunk → embed → store
- [ ] **PIPE-02**: User can check processing status of a document (queued, processing, completed, failed)
- [ ] **PIPE-03**: Failed processing returns error type, failure stage, and actionable message
- [ ] **PIPE-04**: System stores document metadata in MongoDB (filename, size, type, upload time, status, tenant)
- [ ] **PIPE-05**: Health endpoint returns status of all dependencies (MongoDB, Qdrant, Redis)
- [ ] **PIPE-06**: Pipeline emits structured JSON logs per stage with trace ID and timing per document
- [ ] **PIPE-07**: User can delete a document and all its associated vector chunks are removed from Qdrant

### Search & Retrieval

- [ ] **SRCH-01**: User can search their documents via semantic vector similarity (Qdrant cosine search)
- [ ] **SRCH-02**: Search results return top-k ranked chunks with associated document metadata

### Auth & Multi-Tenancy

- [ ] **AUTH-01**: User authenticates via API key in request header
- [ ] **AUTH-02**: Each API key is scoped to a tenant — all operations are tenant-isolated
- [ ] **AUTH-03**: Tenant data is isolated in Qdrant via payload filtering (no cross-tenant data leakage)
- [ ] **AUTH-04**: API enforces rate limiting per API key (Redis token bucket, X-RateLimit headers)

### Infrastructure

- [ ] **INFRA-01**: Docker Compose brings up all services (API, workers, MongoDB, Qdrant, Redis, MinIO)
- [ ] **INFRA-02**: System runs locally without any Azure or cloud dependencies
- [ ] **INFRA-03**: Basic structured logging across all services

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Search Quality

- **SRCH-03**: Hybrid search (vector + BM25 via Qdrant sparse vectors, RRF merge)
- **SRCH-04**: Metadata filtering on search (date, type, tags)
- **SRCH-05**: Source citation in results (document ID, page number, section title)
- **SRCH-06**: Reranking via cross-encoder (ms-marco-MiniLM)

### Extended Formats

- **PARSE-05**: PPTX support via Docling
- **PARSE-06**: XLSX support via Docling
- **PARSE-07**: Table extraction as structured HTML

### Advanced Chunking

- **CHUNK-04**: Semantic chunking (by-title / by-section via Docling HybridChunker)

### Pipeline Extensions

- **PIPE-08**: Webhook/callback POST on pipeline completion
- **PIPE-09**: Batch upload (ZIP or multi-file with shared batch ID)
- **PIPE-10**: Document versioning (re-process on update, keep history)
- **PIPE-11**: Pipeline stage timing metrics

### Tenancy

- **AUTH-05**: Per-tenant usage quotas and metering (doc count, storage, API calls)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| LLM answer generation | Different product domain. Return chunks, let users bring their own LLM. |
| Custom embedding model hosting | GPU hosting complexity. Support configurable embedding API endpoints instead. |
| Real-time document sync (Drive, SharePoint) | OAuth complexity per connector. Users can build sync via upload API. |
| In-browser document viewer | Frontend concern. Return source URLs for native apps. |
| OCR for scanned PDFs | Accuracy/performance concerns. Defer to v2+ as beta. |
| Graph RAG / knowledge graph | Research-grade complexity for marginal gains. |
| Multi-language translation | Testing matrix explosion. Use multilingual embedding models instead. |
| Fine-grained RBAC per document | Tenant-level isolation sufficient for v1. |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PARSE-01 | Phase 2 | Pending |
| PARSE-02 | Phase 2 | Pending |
| PARSE-03 | Phase 2 | Pending |
| PARSE-04 | Phase 2 | Pending |
| CHUNK-01 | Phase 3 | Pending |
| CHUNK-02 | Phase 3 | Pending |
| CHUNK-03 | Phase 3 | Pending |
| PIPE-01 | Phase 3 | Pending |
| PIPE-02 | Phase 6 | Pending |
| PIPE-03 | Phase 6 | Pending |
| PIPE-04 | Phase 2 | Pending |
| PIPE-05 | Phase 1 | Pending |
| PIPE-06 | Phase 6 | Pending |
| PIPE-07 | Phase 4 | Pending |
| SRCH-01 | Phase 4 | Pending |
| SRCH-02 | Phase 4 | Pending |
| AUTH-01 | Phase 5 | Pending |
| AUTH-02 | Phase 5 | Pending |
| AUTH-03 | Phase 5 | Pending |
| AUTH-04 | Phase 5 | Pending |
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 after roadmap creation*
