# Graph RAG

Beyond vector search, DocIngest can build a **knowledge graph** from your corpus — turning unstructured documents into queryable entities, relationships, and topical communities. It's gated behind `GRAPH_RAG_ENABLED` and runs as its own worker, so it never slows the core pipeline.

## How it works

After a document reaches `COMPLETE`, the `graph-worker` runs as a separate ARQ job:

1. **Entity extraction** — spaCy NER over each chunk
2. **Relationships** — subject–verb–object extraction
3. **Deduplication** — entities/relationships merged into a tenant-scoped MongoDB graph store
4. **Communities** (on demand) — Leiden clustering at multiple resolutions, each with a TF-IDF extractive summary

## Enable it

=== "Docker Compose"

    ```bash
    echo "GRAPH_RAG_ENABLED=true" >> .env
    docker compose up --build -d
    ```

=== "Helm"

    ```bash
    helm upgrade docingest ./deploy/helm/docingest --reuse-values \
      --set config.graphRagEnabled=true \
      --set graphWorker.enabled=true
    ```

=== "Local"

    ```bash
    python -m spacy download en_core_web_lg
    export GRAPH_RAG_ENABLED=true
    arq docingest.workers.graph_builder.WorkerSettings
    ```

## Query the graph

When enabled, these endpoints are available (they return `403` when disabled):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/graph/entities` | List entities (paginated) |
| `GET` | `/v1/graph/entities/{id}` | Entity detail + neighbors |
| `GET` | `/v1/graph/communities` | List communities |
| `GET` | `/v1/graph/communities/{id}` | Community detail + members |
| `POST` | `/v1/graph/communities/rebuild` | Rebuild communities (Leiden) |
| `POST` | `/v1/graph/search` | Semantic search over community summaries |

Community detection is **on demand** and tenant-wide — trigger a rebuild after ingesting a batch:

```bash
curl -X POST http://localhost:8000/v1/graph/communities/rebuild \
  -H "X-API-Key: <your-key>"
```

See [Configuration](configuration.md#graph-rag) for tuning knobs.
