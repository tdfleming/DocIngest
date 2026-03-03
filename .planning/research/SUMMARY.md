# Project Research Summary

**Project:** DocIngest
**Domain:** Multi-tenant document ingestion engine / RAG pipeline
**Researched:** 2026-03-03
**Confidence:** HIGH

## Executive Summary

DocIngest is a document ingestion pipeline that converts PDF, HTML, and DOCX files into semantically chunked, vectorized content for RAG and search. Research confirms the existing stack choices (FastAPI, MongoDB, Qdrant, Redis, ARQ, Docling) are sound, but several dependencies need updating: Motor is deprecated (replace with PyMongo Async), LlamaIndex is unnecessary (Docling has built-in chunking via HybridChunker), and Azure services must be replaced with local alternatives (MinIO for blob storage, FastEmbed for embeddings).

The recommended approach is a queue-based async pipeline with stage handoff (convert → chunk+embed), tenant-scoped data isolation, and idempotent processing with content-hash dedup. The highest-risk area is chunking quality — 80% of RAG failures trace to chunking, not retrieval or generation. The second highest risk is multi-tenant data leakage through missing tenant filters, which is application-enforced in Qdrant's payload-based tenancy model.

Key stack changes: remove 5 packages (motor, llama-index-core, llama-index-embeddings-azure-openai, azure-storage-blob, openai), add 4 packages (fastembed, pymongo, beanie, minio), and update version pins on docling (≥2.75) and qdrant-client (≥1.17).

## Key Findings

### Recommended Stack

The existing stack is validated with targeted updates. See [STACK.md](STACK.md) for full details.

**Core technologies:**
- **FastAPI ≥0.115**: No changes needed — async-first, Pydantic v2 native
- **Docling ≥2.75**: Upgrade from ≥2.14 — adds HybridChunker (structure-aware chunking), eliminates LlamaIndex dependency entirely
- **Qdrant ≥1.17**: Upgrade from ≥1.13 — adds built-in BM25 for hybrid search, native FastEmbed integration
- **FastEmbed ≥0.7**: NEW — replaces Azure OpenAI embeddings, ONNX-based (no PyTorch), 384-dim vectors (BAAI/bge-small-en-v1.5)
- **MinIO ≥7.2**: NEW — replaces Azure Blob Storage, S3-compatible API, Docker deployment
- **PyMongo ≥4.10 + Beanie ≥2.0**: NEW — replaces deprecated Motor, native async, Pydantic ODM
- **ARQ ≥0.26**: Keep — maintenance-only but adequate; Taskiq is the migration path if needed

**Critical change:** Vector dimensions shift from 1536 (Azure OpenAI) to 384 (FastEmbed bge-small-en-v1.5). All Qdrant collection configs must be updated.

### Expected Features

See [FEATURES.md](FEATURES.md) for full analysis including competitor comparison.

**Must have (table stakes):**
- PDF, DOCX, HTML, TXT/MD parsing
- Recursive chunking (400-512 tokens, 10-20% overlap)
- Vector embedding + semantic search
- Async pipeline with status tracking
- API key auth with tenant isolation
- Rate limiting, health endpoint, error handling
- Document metadata storage in MongoDB

**Should have (competitive):**
- Hybrid search (vector + BM25) — single highest-impact quality improvement
- Metadata filtering on search
- Document deletion with vector cleanup
- Source citation / provenance tracking
- Webhook on pipeline completion

**Defer (v2+):**
- Reranking (cross-encoder)
- Semantic chunking (by-title/section)
- Table extraction, PPTX/XLSX support
- Document versioning, OCR

**Positioning:** "Full pipeline in a box" — self-hosted Docker Compose that goes upload-to-search. Competitors either sell a platform (Unstructured) or give building blocks to assemble (LlamaIndex, LangChain, Docling).

### Architecture Approach

See [ARCHITECTURE.md](ARCHITECTURE.md) for full diagrams, patterns, and code examples.

**Major components:**
1. **ingestion-api** (FastAPI) — auth, validation, dedup, enqueue, search, health
2. **convert-worker** (ARQ) — Docling PDF/HTML/DOCX → Markdown conversion (CPU-bound)
3. **chunker-worker** (ARQ) — chunking + embedding + Qdrant upsert (IO-bound)
4. **MongoDB** — document metadata, job state, API keys
5. **Qdrant** — vector storage, filtered similarity search
6. **Redis** — ARQ job broker, rate limit counters
7. **MinIO** — raw file + converted content storage

**Key patterns:** Queue-based pipeline with stage handoff, tenant-scoped data isolation (collection-per-tenant for <200 tenants, payload-based for scale), idempotent processing with SHA-256 content-hash dedup.

### Critical Pitfalls

See [PITFALLS.md](PITFALLS.md) for 7 critical pitfalls, integration gotchas, and the "Looks Done But Isn't" checklist.

1. **Chunking destroys semantic coherence** — 80% of RAG failures trace to chunking. Use structure-aware chunking (Docling HybridChunker), not naive fixed-size splitting.
2. **Embedding model lock-in** — changing models requires full re-indexing. Store model version with every vector. Use open-source models you control.
3. **Multi-tenant data leakage** — a single missing tenant filter leaks data. Qdrant's payload filtering is application-enforced. Write isolation tests.
4. **Docling hangs on real-world PDFs** — implement hard timeouts, fallback extraction, and conversion output validation.
5. **Vector collection design breaks at scale** — create payload indexes before data insertion, not after. Missing indexes cause silent full-scan fallback.
6. **FastAPI/worker memory fragmentation** — use jemalloc in Docker containers to prevent OOM kills under concurrent async workloads.
7. **Retrieval silently returns wrong results** — implement hybrid search (BM25 + vectors) before reranking. Measure recall@K.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation — Local Dev Environment
**Rationale:** Nothing works without a running dev environment. Azure dependencies block all testing.
**Delivers:** Docker Compose with all services running locally, updated dependencies, health checks passing
**Addresses:** Local dev requirement, Azure mock requirement
**Avoids:** Premature optimization, feature work before infrastructure works

### Phase 2: Core Pipeline — Upload to Search
**Rationale:** The E2E pipeline is the core value proposition. Must work before anything else matters.
**Delivers:** Working upload → convert → chunk → embed → search pipeline
**Addresses:** E2E pipeline requirement, document conversion, chunking, embedding, search
**Avoids:** Chunking quality pitfall (use Docling HybridChunker), conversion timeout pitfall (implement fallbacks)

### Phase 3: Multi-Tenancy and Auth
**Rationale:** Tenant isolation is a first-class concern per PROJECT.md. Must be designed correctly, not bolted on.
**Delivers:** API key auth, tenant-scoped operations, data isolation verification
**Addresses:** API key auth requirement, tenant isolation
**Avoids:** Data leakage pitfall (mandatory tenant filters, isolation tests)

### Phase 4: Reliability and Testing
**Rationale:** Pipeline must be robust before shipping. Tests validate all previous phases.
**Delivers:** Test suite, error handling, retry logic, conversion fallbacks, status tracking
**Addresses:** Test suite requirement, pipeline reliability
**Avoids:** Silent failures, stuck jobs, untested edge cases

### Phase 5: Search Quality (v1.x)
**Rationale:** Hybrid search is the single highest-impact quality improvement after core pipeline works.
**Delivers:** Hybrid search (BM25 + vectors), metadata filtering, source citations
**Addresses:** Competitive differentiation features
**Avoids:** Retrieval quality pitfall (hybrid before reranking)

### Phase Ordering Rationale

- **Foundation first:** Cannot develop or test without running services
- **Pipeline before auth:** Get the core value working, then layer on isolation
- **Auth before tests:** Tests need tenant isolation to be meaningful
- **Tests before quality features:** Quality improvements need a test harness to validate
- **Dependencies flow forward:** Each phase builds on the previous

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** Docling HybridChunker configuration — need to verify tokenizer alignment with FastEmbed model, optimal chunk size for 384-dim embeddings
- **Phase 5:** Qdrant sparse vector support for BM25 — relatively new feature (v1.17), may need experimentation

Phases with standard patterns (skip research-phase):
- **Phase 1:** Standard Docker Compose setup, well-documented
- **Phase 3:** Qdrant tenant isolation and API key auth are well-documented patterns
- **Phase 4:** Standard Python testing patterns

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations verified against official docs, PyPI releases, and deprecation notices |
| Features | MEDIUM-HIGH | Based on competitor analysis and community consensus; prioritization is subjective |
| Architecture | HIGH | Queue-based pipeline and tenant isolation patterns are well-established and documented |
| Pitfalls | HIGH | Sourced from post-mortems, GitHub issues, and production experience reports (40+ sources) |

**Overall confidence:** HIGH

### Gaps to Address

- **Docling HybridChunker + FastEmbed alignment:** Need to verify tokenizer configuration for bge-small-en-v1.5 with HybridChunker's `max_tokens` parameter
- **Qdrant collection-per-tenant vs payload-based:** DESIGN.md specifies collection-per-tenant; research suggests payload-based is better for most cases. Decision needed during planning.
- **Reranker selection:** TBD in DESIGN.md. Not needed for v1, but should benchmark options (cross-encoder/ms-marco-MiniLM) during v2 planning.
- **PyMongo Async migration:** Motor → AsyncMongoClient migration is straightforward but needs careful testing of all async patterns

## Sources

### Primary (HIGH confidence)
- Docling official docs and PyPI (v2.75.0) — HybridChunker, conversion, multi-format support
- Qdrant official docs (v1.17) — multitenancy, payload indexing, sparse vectors, async API
- FastEmbed GitHub/PyPI (v0.7.1) — ONNX-based embedding, model benchmarks
- Motor deprecation notice (May 2025) — PyMongo Async migration guide
- MinIO Python SDK (v7.2.20) — S3-compatible API for local blob storage
- Beanie ODM (v2.0) — PyMongo Async migration, Pydantic integration
- ARQ docs (v0.27.0) — retry patterns, job timeout handling

### Secondary (MEDIUM confidence)
- 2025 PDF parser benchmarks — Docling 9/10, comparative analysis
- Chunking strategy benchmarks — 512 tokens with overlap consensus
- Competitor analysis (Unstructured, LlamaIndex, LangChain) — feature matrices
- FastAPI memory fragmentation — jemalloc fix (BetterUp engineering blog)

### Tertiary (LOW confidence)
- Reranker model selection — needs domain-specific benchmarking
- FastEmbed vs sentence-transformers performance — hardware-dependent
- Optimal chunk size for 384-dim embeddings — workload-dependent

---
*Research completed: 2026-03-03*
*Ready for roadmap: yes*
