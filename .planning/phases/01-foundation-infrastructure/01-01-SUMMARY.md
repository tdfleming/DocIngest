# Plan 01-01 Summary: Replace Azure with Local Alternatives

## Status: COMPLETE

## What Changed

### Dependencies (pyproject.toml)
- **Removed:** `azure-storage-blob`, `openai`, `llama-index-core`, `llama-index-embeddings-azure-openai`
- **Added:** `minio>=7.2,<8` (S3-compatible blob storage), `fastembed>=0.4,<1` (local embeddings, 384-dim)

### Docker Infrastructure (docker-compose.yml)
- **Added:** MinIO service with health check (`mc ready local`), ports 9000/9001, persistent volume
- **Added:** Health checks on mongodb (`mongosh ping`), qdrant (`curl healthz`), redis (`redis-cli ping`)
- **Updated:** All `depends_on` conditions from `service_started` to `service_healthy`
- **Removed:** `folder-watcher` service and `watch_data` volume
- **Added:** `minio_data` volume

### Configuration (config.py, .env, .env.example)
- **Removed:** All Azure settings (blob connection string, OpenAI endpoint/key/deployment/version)
- **Removed:** `semantic_split_threshold`, `watch_folder`, `watch_poll_interval`
- **Added:** MinIO settings (`minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_secure`, `minio_bucket`)
- **Added:** FastEmbed settings (`fastembed_model` = `BAAI/bge-small-en-v1.5`)
- **Changed:** `embedding_dimensions` from 1536 to 384

### Blob Storage (db/blob.py)
- **Rewritten:** From Azure Blob Storage async client to MinIO sync client
- **Changed:** Single bucket with tenant_id prefix paths (not per-tenant containers)
- **Functions:** `get_blob_client()`, `close_blob()`, `ensure_bucket()`, `upload_blob()`, `download_blob()`, `delete_blob()` -- all now sync

### Embeddings (services/embedding.py)
- **Rewritten:** From Azure OpenAI async client to FastEmbed sync client
- **Functions:** `embed_texts()`, `embed_query()`, `count_tokens()` -- all now sync
- **Model:** `BAAI/bge-small-en-v1.5` (384-dim, ~30MB download on first use)

### Health Endpoint (api/routes/health.py)
- **Fixed:** Return value bug -- now returns `JSONResponse` instead of `(dict, status_code)` tuple
- **Added:** MinIO health check (4th service: mongodb, qdrant, redis, minio)

### App Lifespan (api/app.py)
- **Added:** `ensure_bucket()` call on startup (creates MinIO bucket if missing)
- **Updated:** `close_blob()` call to sync (no longer awaited)

### Workers (workers/converter.py, workers/chunker.py)
- **Updated:** All blob and embedding calls changed from async (await) to sync
- **Updated:** Docstrings to reference MinIO/FastEmbed instead of Azure

### Callers (api/routes/documents.py, api/routes/search.py)
- **Updated:** All `await get_blob_client()`, `await upload_blob()`, `await download_blob()`, `await delete_blob()` calls to sync equivalents
- **Updated:** `await embed_query()` to sync call

## Files Modified
- `pyproject.toml`
- `docker-compose.yml`
- `.env` (created)
- `.env.example`
- `src/docingest/config.py`
- `src/docingest/db/blob.py`
- `src/docingest/services/embedding.py`
- `src/docingest/api/routes/health.py`
- `src/docingest/api/app.py`
- `src/docingest/workers/converter.py`
- `src/docingest/workers/chunker.py`
- `src/docingest/api/routes/documents.py`
- `src/docingest/api/routes/search.py`
- `src/docingest/services/reranker.py` (comment cleanup)

## Verification Results
- [x] `grep -r "azure" src/docingest/` returns no hits
- [x] `grep -r "openai" src/docingest/` returns no hits
- [x] `grep -r "llama.index" src/docingest/` returns no hits
- [x] pyproject.toml has minio and fastembed deps, no Azure/OpenAI/llama-index deps
- [x] docker-compose.yml has minio service with health check
- [x] docker-compose.yml has health checks on mongodb, qdrant, redis
- [x] docker-compose.yml has NO folder-watcher service
- [x] .env exists with local-only settings, no Azure values
- [x] config.py `embedding_dimensions` == 384
- [x] health.py checks 4 services: mongodb, qdrant, redis, minio
- [x] health.py returns JSONResponse (not tuple)
- [x] app.py calls ensure_bucket on startup
- [x] No stale `await` calls on now-sync functions
