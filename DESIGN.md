# DocIngest — Architecture Design Document

## Overview

DocIngest is a multi-tenant document ingestion engine that converts documents (PDF, HTML, DOCX) into semantically chunked, vectorized content for RAG and search use cases. It runs as a containerized pipeline on Docker Swarm.

---

## Scope

| Dimension       | Decision                                                    |
| --------------- | ----------------------------------------------------------- |
| Document types  | PDF, HTML, DOCX (extensible to PPTX/XLSX)                  |
| Ingestion modes | URL fetch, file upload, batch API, watched folder           |
| Scale           | Organization-wide, high concurrency, multi-tenant           |
| Consumers       | RAG (LLM retrieval) + semantic search API                   |
| Auth            | API key per tenant, tenant-scoped data isolation            |
| Embeddings      | Azure OpenAI `text-embedding-3-small` (1536 dimensions)     |
| Chunking        | Structure-aware (Markdown headings) + semantic sub-splitting |
| Deduplication   | SHA-256 content hash, with forced re-process option         |
| File storage    | Azure Blob Storage (raw uploads + converted Markdown)       |
| Search          | Vector similarity + reranking pass                          |

---

## System Architecture

```
                         ┌──────────────┐
                         │   Clients    │
                         │  (API Keys)  │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ ingestion-api│  FastAPI
                         │  (REST API)  │
                         └──┬───┬───┬───┘
                            │   │   │
              ┌─────────────┤   │   ├─────────────┐
              │             │   │   │             │
        ┌─────▼─────┐ ┌────▼───▼───▼────┐ ┌─────▼─────┐
        │  Azure     │ │     Redis       │ │  Qdrant   │
        │  Blob      │ │  (Job Broker)   │ │ (Vectors) │
        │  Storage   │ └────┬───────┬────┘ └───────────┘
        └───────────┘      │       │
                     ┌─────▼──┐ ┌──▼────────┐
                     │convert-│ │ chunker-  │
                     │worker  │ │ worker    │
                     │(Docling│ │(Split +   │
                     │)       │ │ Embed)    │
                     └───┬────┘ └─────┬─────┘
                         │            │
                     ┌───▼────────────▼───┐
                     │      MongoDB       │
                     │  (Document Store)  │
                     └────────────────────┘
```

---

## Multi-Tenancy

- Each API key maps to a `tenant_id` stored in MongoDB `api_keys` collection
- All document records are scoped by `tenant_id`
- Qdrant uses **one collection per tenant** (`tenant_{id}`) for data isolation, independent scaling, and clean deletion
- Azure Blob Storage uses **one container per tenant** (`tenant-{id}`)
- Per-tenant rate limiting at the API layer: 100 req/min default, configurable per key

---

## Data Models

### MongoDB: `api_keys`

```json
{
  "_id": "ObjectId",
  "key_hash": "string (SHA-256 of API key)",
  "tenant_id": "string",
  "tenant_name": "string",
  "rate_limit": 100,
  "enabled": true,
  "created_at": "datetime"
}
```

### MongoDB: `documents`

```json
{
  "_id": "ObjectId",
  "tenant_id": "string",
  "source_hash": "string (SHA-256 of raw content)",
  "source_type": "url | upload | batch | watch",
  "source_ref": "string (URL or original filename)",
  "content_type": "pdf | html | docx",
  "blob_path": "string (Azure Blob path to raw file)",
  "markdown_blob_path": "string (Azure Blob path to converted Markdown)",
  "metadata": {
    "title": "string | null",
    "author": "string | null",
    "page_count": "int | null",
    "word_count": "int",
    "language": "string | null"
  },
  "status": "pending | converting | converted | chunking | complete | failed",
  "error": "string | null",
  "chunk_count": "int",
  "version": "int (increments on re-process)",
  "created_at": "datetime",
  "updated_at": "datetime",
  "processed_at": "datetime | null"
}
```

### Qdrant: per-tenant collection (`tenant_{id}`)

```
Collection config:
  - vectors: size=1536, distance=Cosine
  - on_disk_payload: true (org-scale data)
  - optimizers: indexing_threshold=20000

Point payload:
{
  "doc_id": "string (MongoDB _id)",
  "doc_version": "int",
  "chunk_index": "int",
  "chunk_text": "string",
  "heading_chain": ["string"],
  "source_ref": "string",
  "content_type": "string",
  "char_offset": "int",
  "token_count": "int",
  "created_at": "string (ISO 8601)"
}
```

---

## Processing Pipeline

### Stage 1: Ingestion (API → Redis)

1. API receives request (upload, URL, batch, or watched folder event)
2. Validate auth, resolve tenant
3. Compute `source_hash` from raw content
4. Dedup check: if hash exists for tenant and `force=false`, return existing doc ID
5. Upload raw file to Azure Blob Storage (`tenant-{id}/raw/{doc_id}.{ext}`)
6. Create `documents` record with `status: pending`
7. Enqueue conversion job to Redis via ARQ

### Stage 2: Conversion (converter-worker)

1. Download raw file from Azure Blob
2. Docling converts to clean Markdown (preserving tables, headings, lists)
3. Upload Markdown to Azure Blob (`tenant-{id}/markdown/{doc_id}.md`)
4. Update document record: `status: converted`, populate metadata
5. Enqueue chunking job

### Stage 3: Chunking + Embedding (chunker-worker)

1. Download Markdown from Azure Blob
2. **Pass 1 — Structural split**: Parse Markdown, split on `##` and `###` headings. Each section becomes a candidate chunk with its heading hierarchy preserved.
3. **Pass 2 — Semantic sub-split**: Sections exceeding 512 tokens are split using embedding-similarity-based semantic splitting. 10-15% overlap between sub-chunks within a section. No overlap across section boundaries.
4. **Embed**: Batch chunks (max 2048 tokens each) to Azure OpenAI `text-embedding-3-small`
5. **Upsert**: Write vectors + payloads to Qdrant tenant collection
6. Update document record: `status: complete`, `chunk_count: N`

### Re-processing Flow

1. `POST /v1/documents/{id}/reprocess` with valid API key
2. Delete all Qdrant points where `doc_id == id` for the tenant collection
3. Increment document `version`
4. Set `status: pending`, re-enqueue conversion job
5. New chunks get the updated `doc_version`

---

## Search Pipeline

### `POST /v1/search`

```json
{
  "query": "string",
  "limit": 10,
  "filters": {
    "content_type": ["pdf", "html"],
    "source_ref": "string (partial match)"
  },
  "rerank": true
}
```

### Flow

1. Embed query via Azure OpenAI
2. Qdrant vector search on tenant collection (retrieve `limit * 3` candidates when reranking)
3. Apply payload filters (content_type, source_ref)
4. **Rerank** (when enabled): Pass candidates through a cross-encoder reranker to re-score by semantic relevance. Options:
   - Azure-hosted reranker model
   - Cohere Rerank API
   - Local cross-encoder (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2` via a sidecar service)
5. Return top `limit` results with chunk text, source metadata, and relevance score

### Response

```json
{
  "results": [
    {
      "chunk_text": "string",
      "score": 0.92,
      "doc_id": "string",
      "source_ref": "string",
      "content_type": "pdf",
      "heading_chain": ["Introduction", "Background"],
      "chunk_index": 3
    }
  ],
  "query_tokens": 12,
  "search_time_ms": 45
}
```

---

## API Contract

All endpoints require `X-API-Key` header. Tenant resolved from key.

| Endpoint                          | Method   | Description                          |
| --------------------------------- | -------- | ------------------------------------ |
| `POST /v1/documents`              | Upload   | Single file upload (multipart)       |
| `POST /v1/documents/url`          | Fetch    | Ingest from URL                      |
| `POST /v1/documents/batch`        | Batch    | Multiple files or URL list           |
| `GET /v1/documents/{id}`          | Read     | Document status + metadata           |
| `GET /v1/documents`               | List     | Paginated list, filterable by status |
| `DELETE /v1/documents/{id}`       | Delete   | Remove doc + chunks + blobs          |
| `POST /v1/documents/{id}/reprocess` | Reprocess | Force re-convert and re-chunk     |
| `POST /v1/search`                 | Search   | Semantic search + optional rerank    |
| `GET /v1/health`                  | Health   | Service + dependency health checks   |

### Error Response Format

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document abc123 not found",
    "details": {}
  }
}
```

### Pagination (GET /v1/documents)

```
?page=1&per_page=50&status=complete&content_type=pdf&sort=created_at&order=desc
```

---

## Container Layout

```yaml
services:
  ingestion-api:
    # FastAPI — REST API, auth, rate limiting, validation
    # Ports: 8000
    # Depends: mongodb, redis, qdrant

  converter-worker:
    # Docling — consumes conversion jobs from Redis
    # Concurrency: 4 workers (CPU-bound, Docling is heavy)
    # Depends: mongodb, redis, azure-blob

  chunker-worker:
    # Structural + semantic chunking, Azure OpenAI embedding calls
    # Concurrency: 8 workers (I/O-bound, waiting on Azure API)
    # Depends: mongodb, redis, qdrant, azure-openai

  folder-watcher:
    # Watches mounted volume for new files, submits to API
    # Depends: ingestion-api

  mongodb:
    # Document store + metadata
    # Volume: persistent
    # Ports: 27017 (internal only)

  qdrant:
    # Vector store, per-tenant collections
    # Volume: persistent
    # Ports: 6333 (internal), 6334 (gRPC internal)

  redis:
    # ARQ job broker
    # Ports: 6379 (internal only)
```

---

## Watched Folder

- A `folder-watcher` service monitors a mounted volume (e.g., `/data/inbox/{tenant_id}/`)
- New files detected via filesystem polling (every 30s) or inotify
- Files are submitted to the ingestion API as uploads
- After successful ingestion, files are moved to `/data/inbox/{tenant_id}/processed/`
- Failed files are moved to `/data/inbox/{tenant_id}/failed/` with an error sidecar file

---

## Key Configuration (Environment Variables)

```
# Azure
AZURE_BLOB_CONNECTION_STRING=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# MongoDB
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DATABASE=docingest

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Redis
REDIS_URL=redis://redis:6379

# Processing
CHUNK_MAX_TOKENS=512
CHUNK_OVERLAP_PERCENT=10
SEMANTIC_SPLIT_THRESHOLD=512
EMBEDDING_BATCH_SIZE=100

# Rate Limiting
DEFAULT_RATE_LIMIT=100

# Folder Watcher
WATCH_FOLDER=/data/inbox
WATCH_POLL_INTERVAL=30
```

---

## Technology Stack Summary

| Component       | Technology                          | Purpose                        |
| --------------- | ----------------------------------- | ------------------------------ |
| API Framework   | FastAPI                             | REST API, async, OpenAPI docs  |
| Doc Conversion  | Docling (IBM)                       | PDF/HTML/DOCX → Markdown       |
| Job Queue       | ARQ + Redis                         | Async job processing           |
| Document Store  | MongoDB                             | Raw metadata, job state        |
| Vector Store    | Qdrant                              | Chunk vectors + payload search |
| Embeddings      | Azure OpenAI text-embedding-3-small | 1536-dim vectors               |
| Reranking       | Cross-encoder (TBD provider)        | Search result reranking        |
| File Storage    | Azure Blob Storage                  | Raw files + converted Markdown |
| Folder Watch    | Custom watcher service              | Auto-ingest from mounted dirs  |
| Containerization| Docker Compose / Swarm              | Orchestration                  |
| Language        | Python 3.12+                        | All services                   |

---

## Non-Functional Requirements

- **Idempotency**: All ingestion endpoints are idempotent via source_hash dedup
- **Observability**: Structured JSON logging, health endpoint with dependency checks
- **Resilience**: ARQ retries with exponential backoff (3 attempts), dead letter tracking in MongoDB
- **Security**: API keys hashed at rest, no raw content in logs, tenant isolation enforced at every layer
- **Scalability**: Workers scale horizontally via Docker Swarm replicas
