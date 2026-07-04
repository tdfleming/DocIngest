# Getting Started

## Prerequisites

- Docker & Docker Compose, **or** a Kubernetes cluster + Helm
- ~8 GB RAM for the full stack (16 GB recommended) — Docling loads ~1.5 GB of layout models per converter process

## 1. Start the stack

```bash
git clone https://github.com/tdfleming/DocIngest && cd DocIngest
cp .env.example .env
docker compose up --build
```

This starts the API (`:8000`), frontend (`:3000`), converter/chunker workers, and the datastores (MongoDB, Qdrant, Redis, MinIO).

!!! tip "Before exposing it"
    Change `JWT_SECRET_KEY` and the MinIO credentials in `.env`. Generate a secret with `openssl rand -hex 32`.

## 2. Create a tenant API key

```bash
docker compose exec ingestion-api python scripts/create_api_key.py my-tenant "My Tenant"
```

Copy the key it prints — it's shown once.

## 3. Ingest a document

```bash
curl -X POST http://localhost:8000/v1/documents \
  -H "X-API-Key: <your-key>" \
  -F "file=@document.pdf"
```

Returns `202` with a document `id`. Processing runs asynchronously (convert → chunk → embed → store).

Check status:

```bash
curl http://localhost:8000/v1/documents/<id> -H "X-API-Key: <your-key>"
```

Status moves through `pending → converting → converted → chunking → complete`.

## 4. Search

```bash
curl -X POST http://localhost:8000/v1/search \
  -H "X-API-Key: <your-key>" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "limit": 5}'
```

Results are vector-retrieved and reranked with a local cross-encoder.

## 5. Or use the web UI

Open `http://localhost:3000`, enter your API key on the config screen, and upload / search from the browser.

## Next steps

- [Enable Graph RAG](graph-rag.md) to extract entities and communities
- [Tune configuration](configuration.md) — chunk size, models, rate limits
- [Deploy to production](deployment.md) with Helm and managed datastores
