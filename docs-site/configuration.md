# Configuration

All configuration is via environment variables, loaded through pydantic-settings. See [`.env.example`](https://github.com/tdfleming/DocIngest/blob/master/.env.example) for the full list and defaults.

## Datastores

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URI` | `mongodb://mongodb:27017` | MongoDB connection string |
| `MONGODB_DATABASE` | `docingest` | Database name |
| `QDRANT_HOST` | `qdrant` | Qdrant hostname |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `REDIS_URL` | `redis://redis:6379` | Redis (ARQ queue + rate limiting) |
| `MINIO_ENDPOINT` | `minio:9000` | S3-compatible endpoint |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | `minioadmin` | Object storage credentials |
| `MINIO_BUCKET` | `docingest` | Bucket name |

## Models & processing

| Variable | Default | Description |
|----------|---------|-------------|
| `FASTEMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model (384-dim) |
| `RERANKER_MODEL` | `Xenova/ms-marco-MiniLM-L-6-v2` | Local cross-encoder (~80 MB, ONNX) |
| `CHUNK_MAX_TOKENS` | `512` | Max tokens per chunk |
| `CHUNK_OVERLAP_PERCENT` | `10` | Overlap between chunks |
| `EMBEDDING_DIMENSIONS` | `384` | Embedding vector size |
| `EMBEDDING_BATCH_SIZE` | `100` | Embedding batch size |

## Auth & limits

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | `change-me-in-production` | **Change before exposing.** JWT signing secret |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Access-token lifetime |
| `DEFAULT_RATE_LIMIT` | `100` | Requests/min per API key |

## Graph RAG

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_RAG_ENABLED` | `false` | Master switch for entity extraction, relationships & communities |
| `SPACY_MODEL` | `en_core_web_lg` | spaCy model (graph worker) |
| `ENTITY_CONFIDENCE_THRESHOLD` | `0.7` | Minimum entity confidence |
| `MAX_ENTITIES_PER_CHUNK` | `50` | Cap on entities extracted per chunk |
| `COMMUNITY_RESOLUTIONS` | `[0.1, 0.5, 1.0]` | Leiden resolution levels |

See [Graph RAG](graph-rag.md) for details.
