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
- **Rate limiting** -- Redis token-bucket per API key (fail-open)
- **Observability** -- structured JSON logging with trace IDs and per-stage timing

## Architecture

```
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

**Services:** API server, converter workers (Docling), chunker workers (embed + store), folder watcher

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
```

## API Endpoints

All endpoints require an `X-API-Key` header.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/documents` | Upload a file |
| `POST` | `/v1/documents/url` | Ingest from URL |
| `POST` | `/v1/documents/batch` | Batch ingest |
| `GET` | `/v1/documents` | List documents (paginated) |
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

# Run tests
pytest

# Lint
ruff check src/
```

## Tech Stack

- **API:** FastAPI + Uvicorn
- **Document conversion:** Docling (IBM)
- **Embeddings:** FastEmbed (BAAI/bge-small-en-v1.5)
- **Vector store:** Qdrant
- **Metadata store:** MongoDB
- **Blob storage:** MinIO (S3-compatible)
- **Job queue:** ARQ (async Redis queue)
- **Rate limiting:** Redis token-bucket

## Project Structure

```
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
