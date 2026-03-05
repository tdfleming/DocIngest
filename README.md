# DocIngest

Multi-tenant document ingestion engine that converts documents into semantically chunked, vectorized content for RAG and semantic search.

Upload a PDF, DOCX, HTML, TXT, or Markdown file and DocIngest will convert it to clean Markdown, split it into semantic chunks, generate embeddings, and store everything in a vector database ready for search.

## Features

- **Document conversion** -- PDF, DOCX, HTML to Markdown via IBM Docling; TXT/MD pass-through
- **Two-pass chunking** -- structural split on Markdown headings, then semantic sub-splitting via embeddings
- **Local embeddings** -- FastEmbed with BAAI/bge-small-en-v1.5 (384-dim, no API keys needed)
- **Vector search** -- Qdrant-powered similarity search with optional cross-encoder reranking
- **Multi-tenancy** -- per-tenant API keys, Qdrant collections, and blob storage paths
- **Async pipeline** -- Upload → Convert → Chunk → Embed → Store via ARQ job queue
- **Web UI** -- React frontend for document upload, status tracking, and search
- **Rate limiting** -- Redis token-bucket per API key (fail-open)
- **Observability** -- structured JSON logging with trace IDs and per-stage timing
- **Performance optimized** -- thread-pooled sync I/O, concurrent health checks, batched Qdrant upserts, Lua script caching, collection caching, aggregation-based dashboard stats

## Architecture

```
┌──────────┐     ┌──────────────┐
│  Browser  │────▶│   Frontend   │  :3000
└──────────┘     │  (React UI)  │
                 └──────┬───────┘
                        │
                        ▼
┌──────────┐     ┌──────────────┐     ┌──────────────────┐     ┌─────────┐
│  Client   │────▶│  FastAPI API  │────▶│  Redis (ARQ)      │────▶│ Workers │
└──────────┘     └──────────────┘     └──────────────────┘     └────┬────┘
                                                                     │
                        ┌────────────┬──────────────┬────────────────┘
                        ▼            ▼              ▼
                   ┌─────────┐ ┌─────────┐   ┌──────────┐
                   │ MongoDB │ │  MinIO   │   │  Qdrant  │
                   │ metadata│ │  blobs   │   │ vectors  │
                   └─────────┘ └─────────┘   └──────────┘
```

**Services:** React frontend, API server, converter workers (Docling), chunker workers (embed + store), folder watcher

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env

# 2. Build and start all services
docker compose up --build

# 3. Create an API key for a tenant
docker compose exec ingestion-api python scripts/create_api_key.py my-tenant "My Tenant"

# 4. Upload a document
curl -X POST http://localhost:8000/v1/documents \
  -H "X-API-Key: <your-key>" \
  -F "file=@document.pdf"

# 5. Search
curl -X POST http://localhost:8000/v1/search \
  -H "X-API-Key: <your-key>" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "top_k": 5}'

# Or open the web UI
open http://localhost:3000
```

## API Endpoints

All endpoints require an `X-API-Key` header.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/documents` | Upload a file |
| `POST` | `/v1/documents/url` | Ingest from URL |
| `POST` | `/v1/documents/batch` | Batch ingest (concurrent) |
| `GET` | `/v1/documents` | List documents (paginated) |
| `GET` | `/v1/documents/stats` | Aggregated document counts by status |
| `GET` | `/v1/documents/{id}` | Get document status |
| `DELETE` | `/v1/documents/{id}` | Delete document and chunks |
| `POST` | `/v1/documents/{id}/reprocess` | Re-convert and re-chunk |
| `POST` | `/v1/search` | Semantic vector search |
| `GET` | `/v1/health` | Health check |

Interactive API docs available at `/docs` (Swagger UI) and `/redoc`.

## Configuration

Environment variables (see `.env.example` for defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URI` | `mongodb://mongodb:27017` | MongoDB connection string |
| `MONGODB_DATABASE` | `docingest` | Database name |
| `QDRANT_HOST` | `qdrant` | Qdrant hostname |
| `QDRANT_PORT` | `6333` | Qdrant gRPC port |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `MINIO_BUCKET` | `docingest` | MinIO bucket name |
| `FASTEMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model |
| `CHUNK_MAX_TOKENS` | `512` | Max tokens per chunk |
| `CHUNK_OVERLAP_PERCENT` | `10` | Overlap between chunks |
| `EMBEDDING_DIMENSIONS` | `384` | Embedding vector size |
| `EMBEDDING_BATCH_SIZE` | `100` | Embedding batch size |
| `DEFAULT_RATE_LIMIT` | `100` | Requests/min per API key |

## Hardware Requirements

### Per-service memory profile

| Service | Min RAM | Recommended RAM | Notes |
|---------|---------|-----------------|-------|
| `frontend` | 128 MB | 256 MB | Static file server |
| `ingestion-api` | 256 MB | 512 MB | FastAPI + Uvicorn |
| `converter-worker` ×2 | **2 GB each** | **4 GB each** | Docling loads layout, table structure, and reading-order ML models at startup (~1.5 GB model weight per process) |
| `chunker-worker` ×2 | 512 MB each | 1 GB each | FastEmbed ONNX model ~130 MB; remainder is batch buffers |
| `mongodb` | 512 MB | 2 GB | Working set should fit in RAM for index scans |
| `qdrant` | 1 GB | 4 GB | HNSW index is on-disk; RAM used for OS page cache and active segments |
| `redis` | 256 MB | 512 MB | Job payloads only; not a data store |
| `minio` | 256 MB | 512 MB | Disk I/O bound |
| **Total** | **~8 GB** | **~16 GB** | |

### Minimum (development / low volume)

- **CPU:** 4 cores
- **RAM:** 8 GB
- **Storage:** 20 GB SSD
- **GPU:** Not required

Expect converter throughput of roughly 1–3 pages/second on a modern laptop CPU. Docling's first run downloads ~1.5 GB of model weights; FastEmbed downloads ~130 MB.

### Recommended (production)

- **CPU:** 8+ cores — Docling benefits from thread parallelism within a single document; more cores also allow running more worker replicas
- **RAM:** 16 GB — headroom for two Docling processes (up to 8 GB combined), Qdrant page-cache, and MongoDB working set
- **Storage:** 100 GB+ NVMe SSD — Qdrant on-disk vectors for bge-small-en-v1.5 (384 dimensions) occupy ~1.5 KB per chunk including HNSW overhead; 1 M chunks ≈ 6–8 GB; MinIO holds raw source files plus converted Markdown
- **GPU:** Optional but significant for high-volume ingestion

### GPU acceleration

Docling supports CUDA for layout detection and OCR, giving a **5–10× throughput improvement** on large or scanned PDFs. FastEmbed ONNX inference also runs on CUDA.

Requirements when enabling GPU:

- NVIDIA GPU with **8 GB+ VRAM** (e.g. RTX 3070/4070, A10, L4)
- CUDA 12.x and matching `nvidia-container-toolkit` for Docker

To enable, set the following in `.env` and rebuild the converter image:

```
USE_DOCLING_GPU=true
```

### Storage sizing guide

| Asset | Size estimate |
|-------|---------------|
| Raw source file (10 MB PDF) | 10 MB in MinIO |
| Converted Markdown | ~5% of source size |
| Qdrant vectors @ 384 dims | ~1.5 KB per chunk |
| MongoDB document record | ~2 KB per document |

A corpus of 10 000 × 10 MB PDFs (100 GB raw) with ~500 chunks each produces roughly:
- 5 GB Markdown in MinIO
- ~8 GB in Qdrant (5 M vectors)
- ~10 MB in MongoDB

## Performance

The pipeline includes several optimizations to maximize throughput and minimize latency:

**Workers (converter + chunker):**
- Sync operations (Docling conversion, MinIO I/O, FastEmbed embedding) run in thread pools via `run_in_executor` to avoid blocking the async event loop
- Stale Qdrant chunks are deleted before upserting on document reprocessing (version > 1)

**Qdrant:**
- Known collections are cached in-memory to skip redundant `get_collections` RPCs
- Large upserts are batched in chunks of 100 points

**MongoDB:**
- Aggregation-based `GET /v1/documents/stats` endpoint for efficient dashboard stats (replaces client-side filtering of full document lists)
- Compound index on `(tenant_id, content_type)` for filtered queries

**Rate limiter:**
- Lua script registered once at init (`register_script` / `EVALSHA`) instead of sending the full script on every request

**API:**
- Health check runs all 4 service checks concurrently with `asyncio.gather`; sync MinIO call wrapped in executor
- Batch URL ingestion processes URLs concurrently with `asyncio.gather`
- Search endpoint runs sync `embed_query` in thread pool

**Folder watcher:**
- Reuses a single `httpx.AsyncClient` across poll cycles instead of creating/destroying one per file

**Frontend:**
- Dashboard `StatsPanel` uses the new `/documents/stats` aggregation endpoint instead of fetching up to 200 documents and filtering in JS
- `refetchOnWindowFocus` disabled to reduce unnecessary API calls

## Local Development

Requires Python 3.12+.

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Start infrastructure
docker compose up mongodb qdrant redis minio -d

# Run API server
uvicorn docingest.api.app:app --host 0.0.0.0 --port 8000 --reload

# Run workers (separate terminals)
arq docingest.workers.converter.WorkerSettings
arq docingest.workers.chunker.WorkerSettings

# Run frontend dev server
cd frontend && npm install && npm run dev

# Run tests
pytest

# Lint
ruff check src/
```

## Tech Stack

- **API:** FastAPI + Uvicorn
- **Frontend:** React (served on :3000)
- **Document conversion:** Docling (IBM)
- **Embeddings:** FastEmbed (BAAI/bge-small-en-v1.5)
- **Vector store:** Qdrant
- **Metadata store:** MongoDB
- **Blob storage:** MinIO (S3-compatible)
- **Job queue:** ARQ (async Redis queue)
- **Rate limiting:** Redis token-bucket

## Project Structure

```
frontend/               # React web UI
src/docingest/
├── api/                # FastAPI app, auth, middleware, routes
├── db/                 # MongoDB, Qdrant, Redis, MinIO clients
├── models/             # Pydantic data models
├── services/           # Conversion, chunking, embedding, reranking
├── workers/            # ARQ background job workers
└── watcher/            # Watched folder auto-ingestion
```

## License

Proprietary.
