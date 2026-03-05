# CLAUDE.md

## Project Overview

DocIngest is a multi-tenant document ingestion engine that converts documents (PDF, DOCX, HTML, TXT, Markdown) into semantically chunked, vectorized content for RAG and semantic search. It runs as a containerized microservice pipeline.

## Architecture

```
Browser → React Frontend (:3000) → FastAPI API (:8000) → Redis (ARQ job queue) → Workers
                                                                                    │
                                              ┌──────────────┬──────────────────────┘
                                              ▼              ▼                ▼
                                          MongoDB        MinIO (blobs)     Qdrant (vectors)
```

**Services:**
- `ingestion-api` — FastAPI REST API with auth, rate limiting, document management
- `converter-worker` — Docling-based document-to-Markdown conversion (ARQ worker)
- `chunker-worker` — Two-pass chunking + FastEmbed embedding + Qdrant upsert (ARQ worker)
- `frontend` — React/Vite/Chakra UI web application
- `folder-watcher` (watcher) — Monitors directories for auto-ingestion

**Processing pipeline:** Upload → Convert (Docling → Markdown) → Chunk (structural + semantic split) → Embed (FastEmbed) → Store (Qdrant)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.12+, FastAPI, Uvicorn |
| Frontend | React 18, TypeScript, Vite, Chakra UI, TanStack Query |
| Document conversion | Docling (IBM) |
| Embeddings | FastEmbed (BAAI/bge-small-en-v1.5, 384-dim, local) |
| Vector store | Qdrant |
| Metadata store | MongoDB (Motor async driver) |
| Blob storage | MinIO (S3-compatible) |
| Job queue | ARQ (async Redis queue) |
| Auth | API keys (SHA-256 hashed) + JWT (bcrypt passwords) |
| Logging | structlog (JSON output) |
| Containerization | Docker Compose |

## Project Structure

```
src/docingest/
├── api/                  # FastAPI application
│   ├── app.py            # App factory, lifespan, middleware, router mounting
│   ├── auth.py           # API key resolution, JWT auth, rate limiting deps
│   ├── middleware.py      # Rate limit headers, request logging middleware
│   └── routes/           # Endpoint modules: documents, search, health, auth, admin
├── config.py             # Pydantic Settings (env-based configuration)
├── db/                   # Database clients
│   ├── blob.py           # MinIO upload/download helpers
│   ├── mongodb.py        # Motor client, indexes, CRUD helpers
│   ├── qdrant.py         # Qdrant client, collection management, upsert/search
│   └── redis.py          # Redis/ARQ pool management
├── logging_config.py     # structlog JSON configuration
├── models/               # Pydantic data models
│   ├── document.py       # Document, DocumentStatus, ContentType, SourceType enums
│   └── user.py           # User model, UserRole enum
├── services/             # Business logic
│   ├── api_key_service.py
│   ├── app_logger.py     # Application event logging to MongoDB
│   ├── chunking.py       # Two-pass chunker (structural + semantic)
│   ├── conversion.py     # Docling wrapper, metadata extraction
│   ├── embedding.py      # FastEmbed wrapper
│   ├── rate_limiter.py   # Redis token-bucket rate limiter
│   └── reranker.py       # Cross-encoder search reranking
├── watcher/              # Folder watcher for auto-ingestion
│   └── folder.py
└── workers/              # ARQ background workers
    ├── converter.py      # convert_document job (queue: arq:queue:convert)
    └── chunker.py        # chunk_and_embed job (queue: arq:queue:chunk)

frontend/                 # React SPA
├── src/
│   ├── api/              # Axios API client modules
│   ├── components/       # UI components (auth, dashboard, documents, search, layout, logs)
│   └── pages/            # Route pages
├── package.json          # Vite + React + Chakra UI + TanStack Query
└── postcss.config.js     # Tailwind CSS config

docker/                   # Dockerfiles for each service
scripts/                  # Utility scripts (e.g., create_api_key.py)
.planning/                # Development planning docs (phases, milestones, research)
```

## Development Commands

### Prerequisites
- Python 3.12+
- Node.js (for frontend)
- Docker & Docker Compose (for infrastructure services)

### Backend

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Start infrastructure services only
docker compose up mongodb qdrant redis minio -d

# Run API server (with hot reload)
uvicorn docingest.api.app:app --host 0.0.0.0 --port 8000 --reload

# Run converter worker
arq docingest.workers.converter.WorkerSettings

# Run chunker worker
arq docingest.workers.chunker.WorkerSettings

# Run all services via Docker
docker compose up --build
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # Vite dev server
npm run build        # TypeScript check + Vite production build
```

### Testing

```bash
pytest               # Run all tests
```

- Test config: `asyncio_mode = "auto"`, test path: `tests/`
- Framework: pytest + pytest-asyncio

### Linting

```bash
ruff check src/      # Lint Python code
ruff check --fix src/  # Auto-fix lint issues
```

- Ruff config in `pyproject.toml`: target Python 3.12, line length 100
- Rules enabled: E, F, I, N, UP, B, SIM (pyflakes, pycodestyle, isort, naming, upgrades, bugbear, simplify)

## Key Conventions

### Python
- **Config**: All configuration via environment variables, loaded through `pydantic-settings` (`Settings` class in `config.py`). Use `settings.field_name` — never read `os.environ` directly.
- **Async**: The codebase is async throughout. MongoDB uses Motor, Qdrant client is async, Redis/ARQ is async. Use `async/await` consistently.
- **Models**: Pydantic v2 models with `StrEnum` for status/type enums. Document IDs use MongoDB ObjectId strings.
- **Logging**: Use `structlog.get_logger()` — never `print()` or stdlib `logging` directly. Bind context vars (`trace_id`, `doc_id`) for request tracing.
- **Error handling in workers**: Each pipeline stage has individual try/except blocks that set specific `error_type` and `error_stage` fields on the document record before returning.
- **Multi-tenancy**: All data access is scoped by `tenant_id`. Qdrant uses per-tenant collections (`tenant_{id}`). MinIO paths are prefixed by tenant.
- **Auth**: Two auth mechanisms — API key (`X-API-Key` header) for document/search endpoints, JWT Bearer token for user management endpoints. Use `Tenant` dependency for API-key-authenticated routes, `CurrentUser`/`AdminUser` for JWT routes.
- **Thread-pool offloading**: Sync/blocking calls (Docling conversion, MinIO I/O, FastEmbed embedding) are wrapped in `loop.run_in_executor(None, ...)` to avoid blocking the async event loop. Apply this pattern to any new sync library calls in async code paths.
- **Qdrant collection caching**: Known collection names are cached in a module-level `_known_collections` set to skip redundant `get_collections` RPCs. Update this set when creating or deleting collections.
- **Batched Qdrant upserts**: Large point lists are upserted in batches of 100. Use the `batch_size` parameter of `upsert_chunks()`.
- **Rate limiter Lua caching**: The token-bucket Lua script is registered once via `register_script()` at init and called via `EVALSHA`. Do not use raw `eval()` for rate limiting.
- **Concurrent I/O**: Use `asyncio.gather` for independent async operations (e.g., health checks, batch URL ingestion). Prefer concurrent execution over sequential loops.

### Frontend
- **Component library**: Chakra UI v2 with Emotion
- **Data fetching**: TanStack Query (React Query v5) with Axios client; `refetchOnWindowFocus` is disabled globally
- **Routing**: React Router v6
- **Build**: Vite with TypeScript (strict `--noEmit` check on build)

### API Design
- All API routes are versioned under `/v1/`
- Routers are mounted in `api/app.py` with tag-based grouping
- Error responses use `{"error": {"code": "...", "message": "...", "details": {}}}` format
- Rate limiting enforced per API key via Redis token-bucket (fail-open)
- `GET /v1/documents/stats` returns aggregated counts by status (used by dashboard instead of client-side filtering)

### Docker
- Each service has its own Dockerfile in `docker/`
- All services use `.env` file for configuration (see `.env.example`)
- Infrastructure services (MongoDB, Qdrant, Redis, MinIO) have health checks
- Workers run with configurable replicas (default: 2 each)

### ARQ Workers
- Converter worker: queue `arq:queue:convert`, max 4 concurrent jobs, 10-min timeout, 3 retries
- Chunker worker: queue `arq:queue:chunk`, max 8 concurrent jobs, 5-min timeout, 3 retries
- Workers are started with: `arq docingest.workers.<module>.WorkerSettings`

## Environment Variables

See `.env.example` for the full list. Key variables:

- `MONGODB_URI`, `MONGODB_DATABASE` — MongoDB connection
- `QDRANT_HOST`, `QDRANT_PORT` — Qdrant vector store
- `REDIS_URL` — Redis for ARQ job queue and rate limiting
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` — Blob storage
- `FASTEMBED_MODEL` — Embedding model name (default: BAAI/bge-small-en-v1.5)
- `CHUNK_MAX_TOKENS`, `CHUNK_OVERLAP_PERCENT` — Chunking parameters
- `EMBEDDING_DIMENSIONS`, `EMBEDDING_BATCH_SIZE` — Embedding config
- `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` — JWT auth config
- `DEFAULT_RATE_LIMIT` — Requests/min per API key
