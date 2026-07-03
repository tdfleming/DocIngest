# DocIngest

**The open-source ingestion backend for RAG.** Drop-in, multi-tenant: document → clean Markdown → semantic chunks → vectors → knowledge graph. Self-host it free, or run it managed. Own your data, own your pipeline.

[![CI](https://github.com/tdfleming/DocIngest/actions/workflows/ci.yml/badge.svg)](https://github.com/tdfleming/DocIngest/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)

Point DocIngest at a PDF, DOCX, HTML, TXT, or Markdown file and it converts to clean Markdown, splits into semantic chunks, generates embeddings locally (no API keys), stores them in Qdrant, and — optionally — extracts an entity/relationship knowledge graph. Every layer is tenant-isolated. Run the whole stack with one `docker compose up` or `helm install`.

```bash
docker compose up --build        # full stack, batteries included
```

- **[Quick Start](#quick-start)** · **[Why DocIngest](#why-docingest)** · **[API](#api-endpoints)** · **[Graph RAG](#graph-rag-optional)** · **[Deployment](#deployment)** · **[Configuration](#configuration)**

## Why DocIngest

Ingestion is the ugliest, most re-invented part of every RAG stack — and the layer you re-index again and again as chunking and embedding strategies change. DocIngest packages it as a real, self-hostable service:

| | DocIngest | Unstructured | Ragie | LlamaCloud | RAGFlow |
|---|:---:|:---:|:---:|:---:|:---:|
| Open source | ✅ Apache-2.0 | partial | ❌ | ❌ | ✅ |
| Self-host | ✅ | ✅ | ❌ | ❌ | ✅ |
| Parse → chunk → embed → **serve search** | ✅ | parse only | ✅ | parse-centric | ✅ |
| Built-in **multi-tenant isolation** | ✅ | ❌ | ❌ | ❌ | limited |
| **Knowledge graph** (entities + communities) | ✅ | ❌ | ❌ | limited | ✅ |
| Local embeddings (no per-token cost) | ✅ | — | ❌ | ❌ | configurable |
| Managed cloud option | 🔜 | ✅ | ✅ | ✅ | ✅ |

The combination — permissive OSS **and** real multi-tenancy **and** a graph layer **and** a managed path — is what sets DocIngest apart.

## Features

- **Document conversion** -- PDF, DOCX, HTML to Markdown via IBM Docling; TXT/MD pass-through
- **Two-pass chunking** -- structural split on Markdown headings, then semantic sub-splitting via embeddings
- **Local embeddings** -- FastEmbed with BAAI/bge-small-en-v1.5 (384-dim, no API keys needed)
- **Vector search** -- Qdrant-powered similarity search with local cross-encoder reranking (`ms-marco-MiniLM`)
- **Graph RAG** (optional) -- spaCy entity & relationship extraction plus Leiden community detection with extractive summaries, exposed via `/v1/graph/*`
- **Multi-tenancy** -- per-tenant API keys, Qdrant collections, and blob storage paths
- **Async pipeline** -- Upload → Convert → Chunk → Embed → Store → (optional) Build Graph via ARQ job queue
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

**Services:** React frontend, API server, converter workers (Docling), chunker workers (embed + store), graph worker (spaCy entities + Leiden communities → MongoDB graph store, optional), folder watcher

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

DocIngest uses two auth mechanisms: **API keys** (`X-API-Key` header) for document/search/graph endpoints, and **JWT** (`Authorization: Bearer …`) for user & key management.

**Documents & search** (API key)

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
| `POST` | `/v1/search` | Semantic vector search + reranking |
| `GET` | `/v1/health` | Health check (no auth) |

**Graph RAG** (API key; requires `GRAPH_RAG_ENABLED=true`, else `403`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/graph/entities` | List entities (paginated) |
| `GET` | `/v1/graph/entities/{id}` | Entity detail + neighbors |
| `GET` | `/v1/graph/communities` | List communities |
| `GET` | `/v1/graph/communities/{id}` | Community detail + members |
| `POST` | `/v1/graph/communities/rebuild` | Rebuild communities (Leiden) |
| `POST` | `/v1/graph/search` | Semantic search over community summaries |

**Auth & admin** (JWT): `/v1/auth/*` (login, bootstrap, `/me`, user CRUD) and `/v1/admin/*` (application logs, API-key management).

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
| `RERANKER_MODEL` | `Xenova/ms-marco-MiniLM-L-6-v2` | Local cross-encoder for reranking (~80 MB, ONNX) |
| `CHUNK_MAX_TOKENS` | `512` | Max tokens per chunk |
| `CHUNK_OVERLAP_PERCENT` | `10` | Overlap between chunks |
| `EMBEDDING_DIMENSIONS` | `384` | Embedding vector size |
| `EMBEDDING_BATCH_SIZE` | `100` | Embedding batch size |
| `DEFAULT_RATE_LIMIT` | `100` | Requests/min per API key |
| `GRAPH_RAG_ENABLED` | `false` | Master switch for entity extraction, relationships & communities |
| `SPACY_MODEL` | `en_core_web_lg` | spaCy model for entity extraction (graph worker) |

## Graph RAG (optional)

Beyond vector search, DocIngest can build a **knowledge graph** from your corpus — turning unstructured documents into queryable entities, relationships, and topical communities. It's gated behind `GRAPH_RAG_ENABLED` and runs as its own worker, so it never slows the core pipeline.

**Pipeline:** after a document completes, the `graph-worker` runs spaCy NER + subject-verb-object relationship extraction, deduplicates entities into a tenant-scoped MongoDB graph store, then — on demand — clusters them with the Leiden algorithm at multiple resolutions and writes TF-IDF extractive summaries for each community.

**Enable it:**

```bash
# Docker Compose — the graph-worker service is included; just flip the flag
echo "GRAPH_RAG_ENABLED=true" >> .env
docker compose up --build -d

# Helm
helm upgrade docingest ./deploy/helm/docingest --reuse-values \
  --set config.graphRagEnabled=true --set graphWorker.enabled=true

# Local — install the spaCy model, then run the worker
python -m spacy download en_core_web_lg
arq docingest.workers.graph_builder.WorkerSettings
```

Then explore the graph via `GET /v1/graph/entities`, `GET /v1/graph/communities`, and `POST /v1/graph/communities/rebuild`. See [CLAUDE.md](CLAUDE.md#graph-rag-optional-feature) for tuning knobs.

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
- **Reranking:** FastEmbed cross-encoder (`ms-marco-MiniLM`)
- **Graph RAG:** spaCy (`en_core_web_lg`) + python-igraph / leidenalg

## Project Structure

```
frontend/               # React web UI
src/docingest/
├── api/                # FastAPI app, auth, middleware, routes
├── db/                 # MongoDB, Qdrant, Redis, MinIO clients
├── models/             # Pydantic data models
├── services/           # Conversion, chunking, embedding, reranking, entity extraction, community detection
├── workers/            # ARQ workers: converter, chunker, graph builder
└── watcher/            # Watched folder auto-ingestion
```

## Deployment

### Docker Compose (single server)

The simplest deployment uses Docker Compose on a single machine:

```bash
# 1. Clone and configure
git clone <repo-url> && cd DocIngest
cp .env.example .env
# Edit .env — at minimum change JWT_SECRET_KEY and MinIO credentials
```

**Production `.env` checklist:**

| Variable | Action |
|----------|--------|
| `JWT_SECRET_KEY` | Set to a strong random secret (`openssl rand -hex 32`) |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Change from defaults |
| `DEFAULT_RATE_LIMIT` | Tune per your expected load |

```bash
# 2. Build and launch
docker compose up --build -d

# 3. Verify all services are healthy
docker compose ps

# 4. Create your first tenant API key
docker compose exec ingestion-api python scripts/create_api_key.py my-tenant "My Tenant"
```

### Kubernetes (Helm)

A Kubernetes-agnostic Helm chart lives in [`deploy/helm/docingest`](deploy/helm/docingest). It deploys the API, workers, and frontend, with bundled MongoDB/Qdrant/Redis/MinIO enabled by default for parity with Compose:

```bash
helm install docingest ./deploy/helm/docingest \
  --namespace docingest --create-namespace \
  --set secrets.jwtSecretKey="$(openssl rand -hex 32)"
```

For production, disable the bundled datastores and point at managed services (MongoDB Atlas, Qdrant Cloud, managed Redis, S3) via a values file. See the [chart README](deploy/helm/docingest/README.md) for the full values reference, ingress setup, autoscaling, and image build/push instructions.

### Scaling workers

Converter and chunker workers can be scaled independently to match your workload:

```bash
# Scale converter workers (CPU/GPU intensive — document conversion)
docker compose up --scale converter-worker=4 -d

# Scale chunker workers (lighter — embedding + vector upsert)
docker compose up --scale chunker-worker=4 -d
```

Default is 2 replicas each. Scale converter workers based on document volume and available CPU/RAM (each needs ~2–4 GB). Scale chunker workers based on chunk throughput needs.

### Reverse proxy

In production, place a reverse proxy (Nginx, Caddy, Traefik) in front of the API and frontend:

- Terminate TLS at the proxy
- Forward `/v1/` to `ingestion-api:8000`
- Forward `/` to `frontend:3000`
- Set appropriate `proxy_read_timeout` values — document conversion can take minutes for large files

Example Nginx snippet:

```nginx
server {
    listen 443 ssl;
    server_name docingest.example.com;

    ssl_certificate     /etc/ssl/certs/docingest.pem;
    ssl_certificate_key /etc/ssl/private/docingest.key;

    client_max_body_size 100M;

    location /v1/ {
        proxy_pass http://ingestion-api:8000;
        proxy_read_timeout 600s;
    }

    location / {
        proxy_pass http://frontend:3000;
    }
}
```

### Data persistence

All stateful services use named Docker volumes:

| Volume | Service | Contains |
|--------|---------|----------|
| `mongo_data` | MongoDB | Document metadata, user accounts |
| `qdrant_data` | Qdrant | Vector indexes and stored vectors |
| `redis_data` | Redis | Job queue state (ephemeral) |
| `minio_data` | MinIO | Raw uploaded files, converted Markdown |

**Backup strategy:**
- **MongoDB:** Use `mongodump` on a schedule — small dataset, fast to back up
- **Qdrant:** Snapshot via the [Qdrant snapshot API](https://qdrant.tech/documentation/concepts/snapshots/) or back up the volume directly
- **MinIO:** Use `mc mirror` to replicate to another S3-compatible target, or back up the volume
- **Redis:** Mostly ephemeral job state; loss means in-flight jobs need re-enqueue but no data loss

### Health monitoring

The `GET /v1/health` endpoint checks connectivity to all four backing services (MongoDB, Qdrant, Redis, MinIO) concurrently and returns per-service status. Use it as a liveness/readiness probe:

```bash
curl http://localhost:8000/v1/health
```

### GPU-accelerated deployment

For high-volume ingestion, enable GPU acceleration on converter workers:

1. Install `nvidia-container-toolkit` on the host
2. Set `USE_DOCLING_GPU=true` in `.env`
3. Add GPU resource reservations to the converter service in `docker-compose.yml`:

```yaml
converter-worker:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

See the [Hardware Requirements](#hardware-requirements) section for GPU sizing guidance.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

The self-hosted core is open source under Apache-2.0. Managed cloud hosting,
SSO/SAML, audit logging, usage metering, and HA/Kubernetes deployment are
offered separately as part of the DocIngest cloud/enterprise tier.
