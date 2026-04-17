# Phase 10: Graph Builder Worker - Research

**Researched:** 2026-04-12
**Domain:** ARQ worker pipeline, Qdrant scroll API, MongoDB graph store integration
**Confidence:** HIGH

## Summary

Phase 10 adds a new ARQ worker stage (`graph-worker`) that runs after the chunker completes, extracting entities and relationships from document chunks and persisting them to the MongoDB knowledge graph. The existing codebase already provides all necessary infrastructure: graph data models (Phase 8), graph store CRUD operations (`db/graph_store.py`), and the entity extraction service specification (Phase 9, planned but not yet built).

The worker follows the exact same pattern as `converter.py` and `chunker.py` -- an async job function with staged try/except error handling, `structlog` context vars, status updates, and a `WorkerSettings` class. The key new element is a Qdrant scroll helper to retrieve all chunk payloads for a document, and the orchestration logic to pipe chunk text through entity extraction and into the graph store.

**Primary recommendation:** Follow the converter worker pattern exactly (it demonstrates the enqueue-next-stage pattern), add a `get_doc_chunks` scroll helper to `db/qdrant.py`, and wire the chunker to conditionally enqueue `build_graph` jobs based on `settings.graph_rag_enabled`.

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| arq | >=0.26,<1 | Async Redis job queue | Already used for converter + chunker workers |
| motor | >=3.7,<4 | Async MongoDB driver | Already used throughout |
| qdrant-client | >=1.13,<2 | Async vector store client | Already used, provides scroll API |
| spacy | >=3.7,<4 | NLP entity extraction | Declared in Phase 9 plan (pyproject.toml) |
| structlog | >=24.4,<25 | Structured logging | Project standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| en_core_web_lg | (spacy model) | Production NER model | Downloaded at Docker build time |

No new pip dependencies are needed beyond what Phase 9 adds (spacy).

## Architecture Patterns

### Existing ARQ Worker Pattern (from converter.py and chunker.py)

Every worker in this project follows this exact structure:

```
1. configure_logging() at module level (before other imports)
2. Async job function: (ctx, doc_id, tenant_id, trace_id)
3. Get DB/service clients at top of function
4. structlog.contextvars.bind_contextvars(trace_id, doc_id)
5. Staged try/except blocks with specific error_type + error_stage
6. Status updates via update_document_status()
7. log_event() fire-and-forget via asyncio.create_task()
8. structlog.contextvars.unbind_contextvars() in finally block
9. WorkerSettings class with: functions, redis_settings, queue_name, max_jobs, job_timeout, max_tries, retry_delay
```

### Enqueue-Next-Stage Pattern (from converter.py lines 151-158)

The converter enqueues the chunker after success:

```python
pool = await get_redis_pool()
await pool.enqueue_job(
    "chunk_and_embed",
    doc_id=doc_id,
    tenant_id=tenant_id,
    trace_id=trace_id,
    _queue_name="arq:queue:chunk",
)
```

The chunker will need the same pattern to enqueue `build_graph` conditionally:

```python
if settings.graph_rag_enabled:
    pool = await get_redis_pool()
    await pool.enqueue_job(
        "build_graph",
        doc_id=doc_id,
        tenant_id=tenant_id,
        trace_id=trace_id,
        _queue_name="arq:queue:graph",
    )
```

### Qdrant Scroll API for Fetching All Chunks

The `AsyncQdrantClient.scroll()` method retrieves points by filter without similarity search. It returns `(points, next_offset)` for pagination.

```python
async def get_doc_chunks(
    client: AsyncQdrantClient,
    tenant_id: str,
    doc_id: str,
) -> list:
    """Scroll through all chunks for a doc_id in a tenant collection."""
    name = _collection_name(tenant_id)
    all_points = []
    offset = None

    while True:
        points, next_offset = await client.scroll(
            collection_name=name,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        all_points.extend(points)
        if next_offset is None:
            break
        offset = next_offset

    return all_points
```

Key details:
- `scroll_filter` (not `query_filter`) is the parameter name for scroll
- `with_vectors=False` since we only need payload text, not embeddings
- Returns `(List[Record], Optional[PointId])` -- the second element is the next page offset
- `limit=100` per page is reasonable batch size
- Existing `Filter`, `FieldCondition`, `MatchValue` imports in qdrant.py already cover what's needed

### Graph Builder Worker Flow

```
build_graph(ctx, doc_id, tenant_id, trace_id):
  1. Fetch document from MongoDB -- verify status == COMPLETE
  2. get_doc_chunks(qdrant, tenant_id, doc_id) -- scroll all chunk payloads
  3. For each chunk:
     a. extract_entities_async(chunk.payload["chunk_text"])
     b. extract_relationships_async(chunk.payload["chunk_text"], entities)
     c. For each entity: resolve_entity() against existing tenant entities
     d. upsert_entity() to graph_store
     e. upsert_relationship() to graph_store
  4. Update document: graph_status="complete", entity_count, relationship_count
```

### Recommended Project Structure Addition

```
src/docingest/
  workers/
    converter.py       # existing
    chunker.py         # existing (modified: enqueue graph job)
    graph_builder.py   # NEW
  db/
    qdrant.py          # modified: add get_doc_chunks
  models/
    document.py        # modified: add graph_status, entity_count, relationship_count

docker/
  graph-worker.Dockerfile  # NEW
```

### Anti-Patterns to Avoid
- **Processing all chunks sequentially in one giant loop:** Use batched processing but keep entity resolution sequential per chunk to avoid race conditions on dedup.
- **Not checking settings.graph_rag_enabled:** The feature flag must gate the enqueue in chunker.py AND should be checked early in the graph worker itself (belt-and-suspenders).
- **Blocking the event loop with spaCy:** All spaCy calls MUST go through `run_in_executor` (the entity_extraction service's async wrappers handle this).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Entity dedup/merge | Custom string matching | `graph_store.upsert_entity` with `$addToSet` | Already handles merge of doc_ids, chunk_ids, aliases atomically |
| Entity fuzzy matching | Custom NLP matching | `entity_extraction.resolve_entity` (difflib) | Phase 9 builds this; handles type enforcement |
| Qdrant pagination | Custom offset tracking | `client.scroll()` with next_offset | Built-in cursor-based pagination |
| Graph index management | Manual index creation | `ensure_graph_indexes()` in mongodb.py | Already called conditionally when graph_rag_enabled |

## Common Pitfalls

### Pitfall 1: Entity Extraction Service Not Yet Built
**What goes wrong:** Phase 9 (entity extraction) is planned but not yet implemented. The graph builder depends on `extract_entities_async`, `extract_relationships_async`, and `resolve_entity` from `docingest.services.entity_extraction`.
**Why it happens:** Phase ordering -- Phase 10 cannot be executed before Phase 9 completes.
**How to avoid:** Phase 10 plan MUST declare a dependency on Phase 9 completion. The plan should reference the exact function signatures from the Phase 9 plan.
**Warning signs:** ImportError on `docingest.services.entity_extraction`.

### Pitfall 2: Scroll API Parameter Name
**What goes wrong:** Using `query_filter` instead of `scroll_filter` for the scroll method.
**Why it happens:** The search API uses `query_filter` but scroll uses `scroll_filter`.
**How to avoid:** Use the exact parameter name `scroll_filter` as documented.
**Warning signs:** TypeError or unexpected empty results from scroll.

### Pitfall 3: Chunk ID Tracking
**What goes wrong:** Entities and relationships need `chunk_ids` for provenance, but Qdrant point IDs (UUIDs) are generated at upsert time in the chunker and stored as the point's `id` field, not in the payload.
**Why it happens:** The chunker generates `uuid.uuid4()` for each point but does not store it in the payload.
**How to avoid:** When scrolling chunks, use `point.id` (the Qdrant point ID) as the chunk_id for graph store operations. The scroll response includes both `point.id` and `point.payload`.
**Warning signs:** Empty chunk_ids arrays in entities/relationships.

### Pitfall 4: Document Status After Graph Building
**What goes wrong:** Overwriting the COMPLETE status or creating a new status enum value that breaks the existing frontend/API.
**Why it happens:** The document is already COMPLETE after chunking.
**How to avoid:** Do NOT change `status` -- keep it as COMPLETE. Use the new `graph_status` field (a plain string, not a DocumentStatus enum value) to track graph building progress. Values: None (not started), "building", "complete", "failed".
**Warning signs:** Frontend showing wrong document status; documents stuck in non-COMPLETE state.

### Pitfall 5: Large Document Entity Resolution Performance
**What goes wrong:** For documents with many chunks, calling `find_entities_by_names` for every single chunk creates N MongoDB queries.
**Why it happens:** Naive implementation resolves entities per-chunk against the full tenant graph.
**How to avoid:** Batch entity resolution -- collect all extracted entities from all chunks first, then do a single `find_entities_by_names` call with all unique names, then resolve locally. Only then upsert.
**Warning signs:** Graph building taking 10x longer than expected; MongoDB query count explosion.

### Pitfall 6: Import Ordering with configure_logging
**What goes wrong:** Logging not configured before structlog calls.
**Why it happens:** All existing workers call `configure_logging()` at module level BEFORE importing other docingest modules (with `# noqa: E402` comments).
**How to avoid:** Follow the exact same import pattern as chunker.py -- `configure_logging()` first, then all other imports with noqa comments.
**Warning signs:** Unformatted log output.

## Code Examples

### Worker Function Skeleton (following chunker.py pattern)

```python
"""ARQ worker: knowledge graph construction.

Consumes 'build_graph' jobs from Redis. Fetches chunk payloads from Qdrant,
extracts entities and relationships via spaCy NLP, and upserts them to the
MongoDB graph store.
"""

import asyncio
import time
from datetime import UTC, datetime

import structlog

from docingest.logging_config import configure_logging

configure_logging()

from docingest.config import settings  # noqa: E402
from docingest.db.mongodb import get_db, get_document, update_document_status  # noqa: E402
from docingest.db.qdrant import get_doc_chunks, get_qdrant  # noqa: E402
from docingest.db.redis import get_redis_settings  # noqa: E402
from docingest.db.graph_store import (  # noqa: E402
    find_entities_by_names,
    upsert_entity,
    upsert_relationship,
)
from docingest.models.document import DocumentStatus  # noqa: E402
from docingest.services.app_logger import log_event  # noqa: E402
from docingest.services.entity_extraction import (  # noqa: E402
    extract_entities_async,
    extract_relationships_async,
    resolve_entity,
)

log = structlog.get_logger()


async def build_graph(ctx: dict, doc_id: str, tenant_id: str, trace_id: str = "") -> None:
    db = await get_db()
    qdrant = await get_qdrant()
    structlog.contextvars.bind_contextvars(trace_id=trace_id, doc_id=doc_id)

    try:
        # ... staged processing with try/except blocks ...
        pass
    except Exception as e:
        # ... outer catch-all ...
        pass
    finally:
        structlog.contextvars.unbind_contextvars("trace_id", "doc_id")


class WorkerSettings:
    functions = [build_graph]
    redis_settings = get_redis_settings()
    queue_name = "arq:queue:graph"
    max_jobs = 4
    job_timeout = 600
    max_tries = 2
    retry_delay = 30
```

### Chunker Modification (enqueue graph job)

Add after the COMPLETE status update (line ~206-214 in chunker.py), before the log_event call:

```python
# Enqueue graph building if enabled
if settings.graph_rag_enabled:
    pool = await get_redis_pool()
    await pool.enqueue_job(
        "build_graph",
        doc_id=doc_id,
        tenant_id=tenant_id,
        trace_id=trace_id,
        _queue_name="arq:queue:graph",
    )
```

Requires adding these imports at the top of chunker.py:
```python
from docingest.config import settings  # noqa: E402
from docingest.db.redis import get_redis_pool  # noqa: E402
```

### Document Model Fields Addition

Add to `Document` class in `models/document.py`:
```python
graph_status: str | None = None       # None | "building" | "complete" | "failed"
entity_count: int = 0
relationship_count: int = 0
```

### Docker Compose Service Entry

```yaml
graph-worker:
  build:
    context: .
    dockerfile: docker/graph-worker.Dockerfile
  env_file: .env
  deploy:
    replicas: 1
  depends_on:
    mongodb:
      condition: service_healthy
    redis:
      condition: service_healthy
    qdrant:
      condition: service_healthy
  restart: unless-stopped
```

### Dockerfile Pattern

Based on `chunker.Dockerfile` with spaCy model download added:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir . \
    && python -m spacy download en_core_web_lg

CMD ["arq", "docingest.workers.graph_builder.WorkerSettings"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Qdrant `scroll()` returned `(points, offset)` | Same API, stable since v1.x | Stable | No migration needed |
| ARQ 0.25 patterns | ARQ 0.26+ same API | 2024 | No changes to worker pattern |

## Key Dependency Chain

```
Phase 8 (Graph Data Models) -- COMPLETE
  -> models/graph.py (EntityType, Entity, Relationship, Community)
  -> db/graph_store.py (upsert_entity, upsert_relationship, etc.)

Phase 9 (Entity Extraction) -- NOT YET BUILT
  -> services/entity_extraction.py (extract_entities_async, extract_relationships_async, resolve_entity)
  -> pyproject.toml (spacy dependency)

Phase 10 (Graph Builder Worker) -- THIS PHASE
  -> workers/graph_builder.py (build_graph job)
  -> db/qdrant.py (get_doc_chunks helper)
  -> workers/chunker.py (enqueue build_graph)
  -> models/document.py (graph_status fields)
  -> docker/graph-worker.Dockerfile
  -> docker-compose.yml (graph-worker service)
  -> .env.example (GRAPH_RAG_ENABLED, SPACY_MODEL)
```

Phase 10 MUST NOT be executed before Phase 9 completes. The entity extraction service is a hard dependency.

## Open Questions

1. **No-chunks edge case:** If a document has status COMPLETE but chunk_count=0, the graph builder should log and return early (no graph to build). The chunker already handles this case by setting COMPLETE with chunk_count=0.

2. **Re-processing / versioning:** When a document is re-ingested (version > 1), the chunker deletes old chunks. The graph builder should call `delete_doc_graph_data()` (already exists in graph_store.py) before building the new graph, similar to how chunker calls `delete_doc_chunks`.

3. **Replicas:** Graph building is CPU-heavy (spaCy NLP). Start with 1 replica (not 2 like converter/chunker) since the spaCy model uses ~500MB RAM per process. Can scale later.

## Sources

### Primary (HIGH confidence)
- `src/docingest/workers/converter.py` - Enqueue-next-stage pattern (lines 151-158)
- `src/docingest/workers/chunker.py` - Full ARQ worker pattern, WorkerSettings
- `src/docingest/db/qdrant.py` - Existing Qdrant helpers, Filter/FieldCondition imports
- `src/docingest/db/graph_store.py` - Full graph CRUD API (upsert_entity, upsert_relationship, find_entities_by_names, delete_doc_graph_data)
- `src/docingest/models/graph.py` - EntityType enum, Entity/Relationship/Community models
- `src/docingest/models/document.py` - Document model, DocumentStatus enum
- `src/docingest/config.py` - graph_rag_enabled, spacy_model, entity_confidence_threshold, max_entities_per_chunk settings
- `docker/chunker.Dockerfile` - Base Dockerfile pattern for workers
- `docker-compose.yml` - Service definition pattern

### Secondary (MEDIUM confidence)
- [Qdrant Python Client docs - scroll method](https://python-client.qdrant.tech/qdrant_client.async_qdrant_client) - scroll_filter parameter, return type
- `.planning/phases/09-entity-extraction/09-01-PLAN.md` - Entity extraction service API specification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use, no new dependencies beyond Phase 9's spaCy
- Architecture: HIGH - follows exact patterns from converter.py and chunker.py; graph_store.py API already built
- Pitfalls: HIGH - identified from direct code inspection of existing workers and Qdrant client API

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable -- patterns are established in codebase)
