---
phase: 10-graph-builder-worker
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/docingest/db/qdrant.py
  - src/docingest/models/document.py
  - src/docingest/workers/graph_builder.py
  - src/docingest/workers/chunker.py
  - docker/graph-worker.Dockerfile
  - docker-compose.yml
  - .env.example
autonomous: true
requirements: [GRAPH-WORKER-01, GRAPH-WORKER-02, GRAPH-WORKER-03, GRAPH-WORKER-04, GRAPH-WORKER-05]

must_haves:
  truths:
    - "Document uploaded with GRAPH_RAG_ENABLED=true produces entities and relationships in MongoDB"
    - "Document shows graph_status=complete with accurate entity_count and relationship_count"
    - "GRAPH_RAG_ENABLED=false produces zero graph data and no graph worker enqueue"
    - "graph-worker container starts and processes jobs from arq:queue:graph"
    - "Re-processing a document clears stale graph data before rebuilding"
  artifacts:
    - path: "src/docingest/workers/graph_builder.py"
      provides: "ARQ worker job function build_graph and WorkerSettings"
      exports: ["build_graph", "WorkerSettings"]
    - path: "src/docingest/db/qdrant.py"
      provides: "get_doc_chunks scroll helper"
      exports: ["get_doc_chunks"]
    - path: "src/docingest/models/document.py"
      provides: "graph_status, entity_count, relationship_count fields on Document"
      contains: "graph_status"
    - path: "docker/graph-worker.Dockerfile"
      provides: "Container image for graph worker with spaCy model"
      contains: "graph_builder.WorkerSettings"
    - path: "docker-compose.yml"
      provides: "graph-worker service definition"
      contains: "graph-worker"
  key_links:
    - from: "src/docingest/workers/chunker.py"
      to: "arq:queue:graph"
      via: "enqueue_job('build_graph') when settings.graph_rag_enabled"
      pattern: "enqueue_job.*build_graph.*arq:queue:graph"
    - from: "src/docingest/workers/graph_builder.py"
      to: "src/docingest/db/qdrant.py"
      via: "get_doc_chunks to scroll all chunk payloads"
      pattern: "get_doc_chunks"
    - from: "src/docingest/workers/graph_builder.py"
      to: "src/docingest/db/graph_store.py"
      via: "upsert_entity and upsert_relationship for graph persistence"
      pattern: "upsert_entity|upsert_relationship"
    - from: "src/docingest/workers/graph_builder.py"
      to: "src/docingest/services/entity_extraction.py"
      via: "extract_entities_async and extract_relationships_async for NLP"
      pattern: "extract_entities_async|extract_relationships_async"
---

<objective>
Add the graph builder ARQ worker -- the final pipeline stage that runs after chunking, extracts entities/relationships from chunk text via spaCy NLP, resolves entities against the existing tenant graph, and persists the knowledge graph to MongoDB.

Purpose: Completes the Graph RAG pipeline from document upload through knowledge graph construction, enabling entity-aware retrieval in future phases.

Output: A new `graph_builder.py` worker, Qdrant scroll helper, document model updates, chunker enqueue wiring, Docker service, and env config.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/docingest/workers/chunker.py
@src/docingest/workers/converter.py
@src/docingest/db/qdrant.py
@src/docingest/db/graph_store.py
@src/docingest/services/entity_extraction.py
@src/docingest/models/document.py
@src/docingest/config.py
@src/docingest/db/redis.py
@docker/chunker.Dockerfile
@docker-compose.yml
@.env.example

<interfaces>
<!-- Key types and contracts the executor needs. -->

From src/docingest/services/entity_extraction.py:
```python
async def extract_entities_async(text: str) -> list[dict]:
    # Returns: [{"name": str, "entity_type": EntityType, "start_char": int, "end_char": int}]

async def extract_relationships_async(text: str, entities: list[dict]) -> list[dict]:
    # Returns: [{"source": str, "target": str, "relation_type": str, "description": str}]

def resolve_entity(name: str, entity_type: str, existing: list[dict], threshold: float | None = None) -> str | None:
    # Returns matched entity name or None
```

From src/docingest/db/graph_store.py:
```python
async def upsert_entity(db, tenant_id, name, entity_type, doc_id, chunk_ids, aliases=None) -> str:
async def upsert_relationship(db, tenant_id, source_entity_id, target_entity_id, relation_type, description, doc_id, chunk_ids) -> str:
async def find_entities_by_names(db, tenant_id, names: list[str]) -> list[dict]:
async def delete_doc_graph_data(db, tenant_id, doc_id) -> None:
```

From src/docingest/db/qdrant.py:
```python
# Existing imports already available:
from qdrant_client.models import Filter, FieldCondition, MatchValue
def _collection_name(tenant_id: str) -> str: ...
```

From src/docingest/db/redis.py:
```python
async def get_redis_pool() -> ArqRedis: ...
```

From src/docingest/db/mongodb.py:
```python
async def get_db() -> AsyncIOMotorDatabase: ...
async def get_document(db, doc_id, tenant_id) -> dict | None: ...
async def update_document_status(db, doc_id, status, extra_fields=None) -> None: ...
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add document model fields, Qdrant scroll helper, and env config</name>
  <files>src/docingest/models/document.py, src/docingest/db/qdrant.py, .env.example</files>
  <action>
**1. Modify `src/docingest/models/document.py`** -- Add three fields to the `Document` class, after `chunk_count`:

```python
graph_status: str | None = None       # None | "building" | "complete" | "failed"
entity_count: int = 0
relationship_count: int = 0
```

Do NOT add a new DocumentStatus enum value. `graph_status` is a plain `str | None` field, separate from the `status` enum. This avoids breaking the existing frontend/API.

**2. Modify `src/docingest/db/qdrant.py`** -- Add `get_doc_chunks` function after `delete_doc_chunks`. Uses the Qdrant scroll API with cursor-based pagination to retrieve all chunk payloads for a document:

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

CRITICAL: Use `scroll_filter` (NOT `query_filter`) -- the scroll method uses a different parameter name than the search method.

**3. Modify `.env.example`** -- Append at the end:

```
# Graph RAG
GRAPH_RAG_ENABLED=false
SPACY_MODEL=en_core_web_lg
```
  </action>
  <verify>
    <automated>cd C:/Projects/DocIngest && python -c "from docingest.models.document import Document; d = Document(tenant_id='t', source_hash='h', source_type='upload', source_ref='r', content_type='pdf'); assert d.graph_status is None; assert d.entity_count == 0; assert d.relationship_count == 0; print('OK')" && python -c "from docingest.db.qdrant import get_doc_chunks; print('OK import')" && grep -q "GRAPH_RAG_ENABLED" .env.example && echo "env OK"</automated>
  </verify>
  <done>Document model has graph_status/entity_count/relationship_count fields. Qdrant module exports get_doc_chunks. .env.example has GRAPH_RAG_ENABLED and SPACY_MODEL entries.</done>
</task>

<task type="auto">
  <name>Task 2: Create graph builder worker and wire chunker enqueue</name>
  <files>src/docingest/workers/graph_builder.py, src/docingest/workers/chunker.py</files>
  <action>
**1. Create `src/docingest/workers/graph_builder.py`** -- Follow the exact converter/chunker worker pattern:

Module-level: `configure_logging()` FIRST, then all other imports with `# noqa: E402`.

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
from docingest.db.graph_store import (  # noqa: E402
    delete_doc_graph_data,
    find_entities_by_names,
    upsert_entity,
    upsert_relationship,
)
from docingest.db.mongodb import get_db, get_document, update_document_status  # noqa: E402
from docingest.db.qdrant import get_doc_chunks, get_qdrant  # noqa: E402
from docingest.db.redis import get_redis_settings  # noqa: E402
from docingest.models.document import DocumentStatus  # noqa: E402
from docingest.services.app_logger import log_event  # noqa: E402
from docingest.services.entity_extraction import (  # noqa: E402
    extract_entities_async,
    extract_relationships_async,
    resolve_entity,
)

log = structlog.get_logger()
```

The `build_graph` function signature: `async def build_graph(ctx: dict, doc_id: str, tenant_id: str, trace_id: str = "") -> None:`

Implementation stages (each with its own try/except that sets error_type + error_stage="graph_building"):

**Stage 1: Fetch document and validate**
- `db = await get_db()`, `qdrant = await get_qdrant()`
- `structlog.contextvars.bind_contextvars(trace_id=trace_id, doc_id=doc_id)`
- Belt-and-suspenders: if `not settings.graph_rag_enabled`, log warning and return early
- Fetch doc via `get_document(db, doc_id, tenant_id)` -- if not found, set error and return
- Verify `doc["status"] == DocumentStatus.COMPLETE` -- if not, log warning and return
- Update `graph_status="building"`: `await update_document_status(db, doc_id, doc["status"], extra_fields={"graph_status": "building"})`

**Stage 2: Fetch chunks from Qdrant**
- `chunks = await get_doc_chunks(qdrant, tenant_id, doc_id)`
- If no chunks: update `graph_status="complete"` with counts=0, log, return early
- Log chunk count

**Stage 3: Clear stale graph data (re-processing)**
- If `doc.get("version", 1) > 1` or `doc.get("graph_status") is not None` (re-processing): call `await delete_doc_graph_data(db, tenant_id, doc_id)` and log

**Stage 4: Extract entities and relationships from ALL chunks**
- For each chunk: `text = chunk.payload["chunk_text"]`, `chunk_id = str(chunk.id)`
- Call `extract_entities_async(text)` and then `extract_relationships_async(text, entities)` for each chunk
- Accumulate all extracted entities with their chunk_ids into a list: `all_extracted = []` where each item is `{"name": e["name"], "entity_type": e["entity_type"], "chunk_id": chunk_id}`
- Similarly accumulate all relationships with chunk_ids

**Stage 5: Batch entity resolution and upsert**
- Collect all unique entity names: `unique_names = list({e["name"] for e in all_extracted})`
- Single batch lookup: `existing = await find_entities_by_names(db, tenant_id, unique_names)`
- For each unique (name, entity_type) pair:
  - Call `resolve_entity(name, entity_type, existing)` to check for fuzzy match
  - Use the resolved name if found, otherwise use original name
  - Collect all chunk_ids for this entity across all chunks
  - `entity_id = await upsert_entity(db, tenant_id, resolved_name, entity_type, doc_id, chunk_ids_for_entity)`
  - Store entity_id in a lookup dict keyed by original lowercase name for relationship wiring

**Stage 6: Upsert relationships**
- For each extracted relationship:
  - Look up source_entity_id and target_entity_id from the entity lookup dict (by lowercase source/target name)
  - Skip if either entity not found in lookup
  - `await upsert_relationship(db, tenant_id, source_entity_id, target_entity_id, rel["relation_type"], rel["description"], doc_id, [rel_chunk_id])`
  - Count successful upserts

**Stage 7: Update document with completion**
- `await update_document_status(db, doc_id, DocumentStatus.COMPLETE, extra_fields={"graph_status": "complete", "entity_count": entity_count, "relationship_count": relationship_count, "graph_built_at": datetime.now(UTC)})`
- Fire-and-forget log_event with timing details
- Log completion with entity/relationship counts and elapsed time

**Outer except and finally:** Same pattern as chunker -- catch-all sets `graph_status="failed"`, `error_stage="graph_building"`. Finally block calls `structlog.contextvars.unbind_contextvars("trace_id", "doc_id")`.

**WorkerSettings class:**
```python
class WorkerSettings:
    functions = [build_graph]
    redis_settings = get_redis_settings()
    queue_name = "arq:queue:graph"
    max_jobs = 4
    job_timeout = 600
    max_tries = 2
    retry_delay = 30
```

**2. Modify `src/docingest/workers/chunker.py`** -- Add graph job enqueue after the COMPLETE status update (after line 214, before the log_event asyncio.create_task on line 216).

Add imports (with existing noqa pattern -- add alongside the existing imports at the top, after `configure_logging()`):
```python
from docingest.config import settings  # noqa: E402
from docingest.db.redis import get_redis_pool  # noqa: E402
```

Add enqueue block between the `update_document_status` call (line 206-214) and the `asyncio.create_task(log_event(...))` call (line 216):
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
  </action>
  <verify>
    <automated>cd C:/Projects/DocIngest && python -c "from docingest.workers.graph_builder import build_graph, WorkerSettings; assert WorkerSettings.queue_name == 'arq:queue:graph'; assert WorkerSettings.max_jobs == 4; assert WorkerSettings.job_timeout == 600; print('OK')" && python -c "import ast; tree = ast.parse(open('src/docingest/workers/chunker.py').read()); found = any('graph_rag_enabled' in ast.dump(node) for node in ast.walk(tree)); assert found, 'graph_rag_enabled not in chunker'; print('chunker OK')" && ruff check src/docingest/workers/graph_builder.py src/docingest/workers/chunker.py</automated>
  </verify>
  <done>graph_builder.py worker processes build_graph jobs with full staged error handling. chunker.py conditionally enqueues build_graph when graph_rag_enabled. Both pass ruff linting.</done>
</task>

<task type="auto">
  <name>Task 3: Create Dockerfile and add docker-compose service</name>
  <files>docker/graph-worker.Dockerfile, docker-compose.yml</files>
  <action>
**1. Create `docker/graph-worker.Dockerfile`** -- Based on `docker/chunker.Dockerfile` with spaCy model download:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir . \
    && python -m spacy download en_core_web_lg

CMD ["arq", "docingest.workers.graph_builder.WorkerSettings"]
```

**2. Modify `docker-compose.yml`** -- Add the graph-worker service after the `chunker-worker` service block (before the `mongodb` service). Use 1 replica (not 2) because spaCy model uses ~500MB RAM per process:

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

Note: graph-worker does NOT depend on minio (unlike chunker-worker) since it reads from Qdrant and writes to MongoDB only.
  </action>
  <verify>
    <automated>cd C:/Projects/DocIngest && test -f docker/graph-worker.Dockerfile && grep -q "graph_builder.WorkerSettings" docker/graph-worker.Dockerfile && grep -q "spacy download" docker/graph-worker.Dockerfile && grep -q "graph-worker" docker-compose.yml && grep -A2 "graph-worker" docker-compose.yml | head -5 && echo "OK"</automated>
  </verify>
  <done>graph-worker.Dockerfile exists with spaCy model download. docker-compose.yml has graph-worker service with 1 replica depending on mongodb, redis, qdrant.</done>
</task>

</tasks>

<verification>
1. `python -c "from docingest.workers.graph_builder import build_graph, WorkerSettings; print('worker imports OK')"` -- Worker module loads without errors
2. `python -c "from docingest.db.qdrant import get_doc_chunks; print('qdrant helper OK')"` -- Scroll helper importable
3. `python -c "from docingest.models.document import Document; d = Document(tenant_id='t', source_hash='h', source_type='upload', source_ref='r', content_type='pdf'); assert d.graph_status is None; print('model OK')"` -- Document model has new fields
4. `ruff check src/docingest/workers/graph_builder.py src/docingest/workers/chunker.py src/docingest/db/qdrant.py src/docingest/models/document.py` -- All modified files pass linting
5. `grep -q "graph_rag_enabled" src/docingest/workers/chunker.py` -- Chunker has feature flag gate
6. `grep -q "graph-worker" docker-compose.yml && grep -q "spacy download" docker/graph-worker.Dockerfile` -- Docker config complete
</verification>

<success_criteria>
- graph_builder.py follows the exact ARQ worker pattern (configure_logging first, staged try/except, structlog contextvars, WorkerSettings)
- Chunker conditionally enqueues build_graph only when settings.graph_rag_enabled is true
- Document model has graph_status (str|None), entity_count (int), relationship_count (int)
- get_doc_chunks scrolls Qdrant with scroll_filter (not query_filter), cursor pagination, with_vectors=False
- Entity resolution is batched: single find_entities_by_names call for all unique names, then resolve locally
- Re-processing calls delete_doc_graph_data before rebuilding
- graph-worker Dockerfile includes spacy model download
- docker-compose has graph-worker with 1 replica
- .env.example has GRAPH_RAG_ENABLED and SPACY_MODEL
- All files pass ruff check
</success_criteria>

<output>
After completion, create `.planning/phases/10-graph-builder-worker/10-01-SUMMARY.md`
</output>
