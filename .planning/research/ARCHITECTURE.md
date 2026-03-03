# Architecture Research: Document Ingestion Pipeline for RAG

**Domain:** Multi-tenant document ingestion engine / RAG pipeline
**Date:** 2026-03-03
**Confidence:** HIGH (based on official documentation, production patterns, and established open-source projects)
**Stack:** FastAPI, ARQ+Redis, MongoDB, Qdrant, Docling, Azure OpenAI, Python 3.12+

---

## Standard Architecture

A production RAG ingestion pipeline separates concerns into three layers: an API gateway that accepts documents and serves search results, an asynchronous worker tier that performs CPU/IO-heavy processing, and a storage tier for metadata, vectors, and raw files. Communication between API and workers is mediated by a job queue (Redis/ARQ), giving backpressure control and retry semantics.

```
                         Clients (API Keys)
                                |
                         +------v-------+
                         | ingestion-api|  FastAPI (async)
                         |  validates   |  - auth / tenant resolution
                         |  enqueues    |  - dedup check (SHA-256)
                         |  serves /search  - rate limiting
                         +--+---+---+---+
                            |   |   |
              +-------------+   |   +--------------+
              |                 |                   |
        +-----v------+   +-----v------+   +--------v--------+
        | Azure Blob |   |   Redis    |   |     Qdrant      |
        | Storage    |   | (ARQ Queue)|   |  (Vector Store)  |
        | raw + md   |   +--+-----+---+   +---------+--------+
        +------------+      |     |                  |
                       +----v--+  +---v--------+     |
                       |convert|  |  chunker   |     |
                       |worker |  |  worker    |     |
                       |Docling|  | split+embed|-----+
                       +---+---+  +-----+------+
                           |            |
                       +---v------------v----+
                       |      MongoDB        |
                       |  (metadata + state) |
                       +---------------------+

Data Flow:
  1. Client -> API: upload/URL/batch
  2. API -> Blob: store raw file
  3. API -> MongoDB: create doc record (status: pending)
  4. API -> Redis: enqueue convert job
  5. convert-worker -> Blob: download raw, upload markdown
  6. convert-worker -> MongoDB: update status -> converted
  7. convert-worker -> Redis: enqueue chunk job
  8. chunker-worker -> Blob: download markdown
  9. chunker-worker -> Azure OpenAI: embed chunks
 10. chunker-worker -> Qdrant: upsert vectors
 11. chunker-worker -> MongoDB: update status -> complete
```

---

## Component Responsibilities

| Component         | Responsibility                                    | Scaling Strategy                | Key Dependency       |
|-------------------|---------------------------------------------------|---------------------------------|----------------------|
| ingestion-api     | Auth, validation, dedup, enqueue, search, health  | Horizontal (stateless)          | Redis, MongoDB       |
| convert-worker    | Docling PDF/HTML/DOCX to Markdown conversion      | Horizontal (CPU-bound, ~4 conc) | Blob Storage, Redis  |
| chunker-worker    | Structural + semantic chunking, embedding, upsert | Horizontal (IO-bound, ~8 conc)  | Azure OpenAI, Qdrant |
| MongoDB           | Document metadata, job state, API keys, audit     | Replica set                     | Persistent volume    |
| Qdrant            | Vector storage, filtered similarity search        | Sharding / replicas             | Persistent volume    |
| Redis             | ARQ job broker, rate limit counters               | Sentinel or single node         | In-memory, AOF       |
| Azure Blob        | Raw file + converted Markdown storage             | Managed (Azure)                 | Network              |
| folder-watcher    | Filesystem polling, auto-submit to API            | Single instance per mount       | ingestion-api        |

---

## Recommended Project Structure

This structure is based on the existing codebase layout, validated against FastAPI best practices and the monorepo pattern for shared models between API and workers.

```
docingest/
|-- .planning/                    # Project planning and research (not shipped)
|   |-- research/
|   |   |-- ARCHITECTURE.md       # This file
|   |-- PROJECT.md
|   |-- config.json
|
|-- src/docingest/                # Main Python package
|   |-- __init__.py
|   |-- config.py                 # Pydantic Settings (env vars, defaults)
|   |
|   |-- api/                      # FastAPI application layer
|   |   |-- __init__.py
|   |   |-- app.py                # FastAPI app factory, lifespan, middleware
|   |   |-- auth.py               # API key validation, tenant resolution
|   |   |-- dependencies.py       # Shared FastAPI Depends (db sessions, clients)
|   |   |-- routes/
|   |   |   |-- __init__.py
|   |   |   |-- documents.py      # CRUD + upload + batch + reprocess endpoints
|   |   |   |-- search.py         # Vector search + rerank endpoint
|   |   |   |-- health.py         # Health/readiness checks
|   |
|   |-- models/                   # Pydantic models (shared between API + workers)
|   |   |-- __init__.py
|   |   |-- document.py           # Document, Chunk, SearchResult schemas
|   |   |-- api_key.py            # API key / tenant schemas
|   |   |-- enums.py              # DocumentStatus, ContentType, SourceType enums
|   |
|   |-- services/                 # Business logic (pure functions, no framework deps)
|   |   |-- __init__.py
|   |   |-- conversion.py         # Docling wrapper: raw file -> Markdown
|   |   |-- chunking.py           # Structural split + semantic sub-split
|   |   |-- embedding.py          # Azure OpenAI batch embedding calls
|   |   |-- reranker.py           # Cross-encoder reranking
|   |   |-- dedup.py              # SHA-256 hashing, duplicate detection
|   |
|   |-- workers/                  # ARQ worker definitions (separate processes)
|   |   |-- __init__.py
|   |   |-- converter.py          # Conversion job handler + WorkerSettings
|   |   |-- chunker.py            # Chunking + embedding job handler + WorkerSettings
|   |   |-- shared.py             # Shared startup/shutdown hooks (db connections)
|   |
|   |-- db/                       # Database/storage client wrappers
|   |   |-- __init__.py
|   |   |-- mongodb.py            # Motor async client, CRUD helpers
|   |   |-- qdrant.py             # Qdrant client, collection management
|   |   |-- redis.py              # Redis/ARQ pool management
|   |   |-- blob.py               # Azure Blob (or local mock) storage
|   |
|   |-- watcher/                  # Folder watcher service (optional)
|   |   |-- __init__.py
|   |   |-- folder.py             # Filesystem polling, submit to API
|
|-- docker/                       # Dockerfiles
|   |-- Dockerfile.api
|   |-- Dockerfile.worker
|
|-- scripts/                      # Dev/ops utility scripts
|-- tests/                        # Test suite
|   |-- conftest.py               # Shared fixtures (mock clients, test tenant)
|   |-- test_api/
|   |-- test_services/
|   |-- test_workers/
|
|-- docker-compose.yml
|-- pyproject.toml
|-- DESIGN.md
|-- .env.example
|-- .gitignore
```

**Key structural principle:** Models are shared between API and workers via the `src/docingest/models/` package. Services contain pure business logic with no framework coupling. Workers import services but never import from `api/`. The API imports from services and models but never from workers.

Dependency direction: `api/ -> services/ -> db/` and `workers/ -> services/ -> db/`, with `models/` imported by all.

---

## Architectural Patterns

### Pattern 1: Queue-Based Pipeline with Stage Handoff

**What:** Each processing stage (convert, chunk+embed) is a separate ARQ job. Completion of one stage enqueues the next. The API only enqueues the first stage and returns immediately.

**When to use:** When processing stages have different resource profiles (CPU-bound conversion vs IO-bound embedding), different failure modes, and need independent scaling.

**Trade-offs:**
- (+) Stages scale independently (4 convert workers, 8 chunker workers)
- (+) Partial progress is preserved (converted markdown survives chunker failure)
- (+) Each stage can retry independently
- (-) More complex state tracking (document status must reflect current stage)
- (-) Latency increases with queue hops

**Code example (ARQ job chaining):**

```python
# workers/converter.py
from arq import Retry

async def convert_document(ctx: dict, doc_id: str, tenant_id: str) -> None:
    """Stage 1: Convert raw document to Markdown."""
    db = ctx["mongodb"]
    blob = ctx["blob"]

    await db.update_document_status(doc_id, "converting")

    try:
        raw_bytes = await blob.download(f"{tenant_id}/raw/{doc_id}")
        markdown = await convert_with_docling(raw_bytes)
        await blob.upload(f"{tenant_id}/markdown/{doc_id}.md", markdown)
        await db.update_document_status(doc_id, "converted")

        # Chain to next stage
        redis = ctx["redis"]
        await redis.enqueue_job(
            "chunk_and_embed",
            doc_id=doc_id,
            tenant_id=tenant_id,
        )
    except Exception as e:
        job_try = ctx.get("job_try", 1)
        if job_try < 3:
            raise Retry(defer=job_try * 10)  # 10s, 20s backoff
        await db.update_document_status(doc_id, "failed", error=str(e))
        raise


class WorkerSettings:
    functions = [convert_document]
    max_tries = 3
    job_timeout = 600  # 10 min for large PDFs

    on_startup = startup  # init db, blob clients
    on_shutdown = shutdown
```

### Pattern 2: Tenant-Scoped Data Isolation (Collection-per-Tenant)

**What:** Each tenant gets its own Qdrant collection (`tenant_{id}`) and Azure Blob container (`tenant-{id}`). MongoDB documents are filtered by `tenant_id` field with a compound index.

**When to use:** When tenants require hard data isolation, independent lifecycle management (delete all tenant data cleanly), and when tenant count is moderate (under 1000). This is the pattern chosen in DocIngest's DESIGN.md.

**Trade-offs:**
- (+) Complete data isolation -- no filter bugs can leak data
- (+) Clean tenant deletion (drop collection, delete container)
- (+) Independent collection tuning per tenant (index thresholds, etc.)
- (-) Collection overhead: each Qdrant collection has fixed memory cost
- (-) Not suitable for thousands of tenants (Qdrant Cloud limits to ~1000 collections)
- (-) Cannot do cross-tenant search (rarely needed, but impossible)

**Alternative (payload-based tenancy) for high tenant counts:**

```python
# Qdrant official recommendation for many tenants: single collection, payload filter
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

# Create one collection with tenant-aware indexing
client.create_collection(
    collection_name="documents",
    vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
    hnsw_config=models.HnswConfigDiff(payload_m=16, m=0),  # per-tenant HNSW
)

# Mark tenant_id as tenant field for storage optimization
client.create_payload_index(
    collection_name="documents",
    field_name="tenant_id",
    field_schema=models.KeywordIndexParams(
        type=models.KeywordIndexType.KEYWORD,
        is_tenant=True,  # co-locates same-tenant vectors for fast reads
    ),
)

# Query with mandatory tenant filter
results = client.query_points(
    collection_name="documents",
    query=query_vector,
    query_filter=models.Filter(
        must=[
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value="tenant_abc"),
            )
        ]
    ),
    limit=10,
)
```

**Recommendation for DocIngest:** The collection-per-tenant approach in DESIGN.md is correct for the expected scale (organization-wide, not SaaS with thousands of tenants). If tenant count grows beyond ~200, migrate to payload-based tenancy with `is_tenant=True`.

### Pattern 3: Idempotent Processing with Content-Hash Dedup

**What:** Every document is hashed (SHA-256 of raw content) before processing. The hash is stored in MongoDB and checked on ingestion. Duplicate submissions return the existing document ID without re-processing. A `force=true` flag bypasses dedup for re-processing.

**When to use:** Always, for any document ingestion pipeline. Documents are frequently re-submitted (same URL crawled twice, same file uploaded by different users within a tenant, batch jobs re-run).

**Trade-offs:**
- (+) Prevents wasted compute on duplicate documents
- (+) Makes the API naturally idempotent (safe to retry failed uploads)
- (+) Saves embedding API costs (most expensive part of the pipeline)
- (-) Hash computation adds latency on upload (negligible for files under 100MB)
- (-) Doesn't detect near-duplicates (slightly edited versions get new hashes)

**Code example:**

```python
# services/dedup.py
import hashlib
from io import BytesIO

def compute_content_hash(content: bytes) -> str:
    """SHA-256 hash of raw document content."""
    return hashlib.sha256(content).hexdigest()

# api/routes/documents.py
async def ingest_document(
    file: UploadFile,
    force: bool = False,
    tenant_id: str = Depends(get_tenant_id),
    db: MongoDB = Depends(get_mongodb),
):
    content = await file.read()
    content_hash = compute_content_hash(content)

    if not force:
        existing = await db.find_document_by_hash(tenant_id, content_hash)
        if existing:
            return {"doc_id": str(existing["_id"]), "status": "duplicate"}

    # Proceed with new ingestion...
    doc_id = await db.create_document(tenant_id, content_hash, ...)
    await enqueue_conversion(doc_id, tenant_id)
    return {"doc_id": doc_id, "status": "pending"}
```

---

## Data Flow Diagrams

### Request Flow (API -> Queue -> Worker)

```
Client                  API                    Redis/ARQ            Worker
  |                      |                        |                    |
  |-- POST /v1/docs ---->|                        |                    |
  |                      |-- validate auth ------->                    |
  |                      |-- compute hash -------->                    |
  |                      |-- check dedup (Mongo) ->                    |
  |                      |-- upload to Blob ------>                    |
  |                      |-- create doc (Mongo) -->                    |
  |                      |-- enqueue job -------->|                    |
  |<-- 202 Accepted -----|                        |                    |
  |                      |                        |-- pick up job ---->|
  |                      |                        |                    |-- process
  |                      |                        |                    |-- update Mongo
  |                      |                        |                    |-- enqueue next
  |                      |                        |<--- next job ------|
  |                      |                        |-- pick up job ---->|
  |                      |                        |                    |-- chunk + embed
  |                      |                        |                    |-- upsert Qdrant
  |                      |                        |                    |-- update Mongo
  |                      |                        |                    |
  |-- GET /v1/docs/{id}->|                        |                    |
  |<-- {status:complete}-|                        |                    |
```

### Pipeline Flow (Document State Machine)

```
                    +----------+
                    |  pending  |  (doc created, job enqueued)
                    +----+-----+
                         |
                    +----v--------+
                    | converting  |  (convert-worker processing)
                    +----+--------+
                         |
                    +----v--------+
              +---->| converted   |  (markdown ready, chunk job enqueued)
              |     +----+--------+
              |          |
              |     +----v--------+
              |     |  chunking   |  (chunker-worker processing)
              |     +----+--------+
              |          |
              |     +----v--------+
              |     |  complete   |  (vectors in Qdrant, searchable)
              |     +-------------+
              |
              |     +-------------+
              +-----+   failed    |  (error recorded, retries exhausted)
                    +------+------+
                           |
                    +------v------+
                    | reprocess   |  (manual trigger, re-enters pending)
                    +-------------+

Status transitions (MongoDB `documents.status`):
  pending -> converting -> converted -> chunking -> complete
  any stage -> failed (on error after retries)
  failed/complete -> pending (on reprocess)
```

### State Management (MongoDB Document Lifecycle)

```python
# MongoDB document status tracking
# Each status transition is an atomic update with timestamp

# On ingestion:
{
    "status": "pending",
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
    "error": None,
    "version": 1
}

# On conversion start:
{"$set": {"status": "converting", "updated_at": datetime.utcnow()}}

# On conversion complete:
{"$set": {
    "status": "converted",
    "markdown_blob_path": "tenant-x/markdown/doc123.md",
    "metadata.title": "Extracted Title",
    "metadata.page_count": 12,
    "updated_at": datetime.utcnow()
}}

# On chunking complete:
{"$set": {
    "status": "complete",
    "chunk_count": 47,
    "processed_at": datetime.utcnow(),
    "updated_at": datetime.utcnow()
}}

# On failure (after retries exhausted):
{"$set": {
    "status": "failed",
    "error": "Docling conversion timeout after 600s",
    "updated_at": datetime.utcnow()
}}

# Recommended MongoDB indexes for the documents collection:
# 1. Compound index for tenant + status queries (list documents by status)
db.documents.create_index([("tenant_id", 1), ("status", 1)])
# 2. Compound index for dedup lookups
db.documents.create_index([("tenant_id", 1), ("source_hash", 1)], unique=True)
# 3. Compound index for listing with sort
db.documents.create_index([("tenant_id", 1), ("created_at", -1)])
# 4. API key lookup
db.api_keys.create_index([("key_hash", 1)], unique=True)
```

---

## Scaling Considerations

| Scale             | Users/Tenants | Documents    | Architecture Changes                                                   |
|-------------------|---------------|--------------|------------------------------------------------------------------------|
| **Dev/POC**       | 1-5           | < 1K         | Single docker-compose, 1 worker each, in-memory Qdrant                 |
| **Team**          | 5-20          | 1K-50K       | Persistent volumes, 2-4 convert workers, 4-8 chunker workers           |
| **Department**    | 20-100        | 50K-500K     | MongoDB replica set, Qdrant with on_disk_payload, Redis Sentinel       |
| **Organization**  | 100-500       | 500K-5M      | Multiple API replicas behind load balancer, Qdrant sharding            |
| **Multi-org SaaS**| 500+          | 5M+          | Switch to payload-based Qdrant tenancy, MongoDB sharding, dedicated worker pools per priority |

**Key scaling bottlenecks (in order):**

1. **Embedding API rate limits** -- Azure OpenAI has TPM/RPM limits. Mitigate with batch embedding, request queuing, and multiple deployment slots.
2. **Docling CPU usage** -- PDF conversion is CPU-intensive. Scale convert-workers horizontally; each needs 2-4 CPU cores.
3. **Qdrant memory** -- Vector storage grows linearly with chunk count. Enable `on_disk_payload: true` and use `mmap` storage for large deployments.
4. **MongoDB write contention** -- Status updates from many workers. Use write concern `w:1` for status updates (not critical data), `w:majority` for document creation.

---

## Anti-Patterns

### Anti-Pattern 1: Synchronous Document Processing in API Request

**What:** Processing the document (convert + chunk + embed) within the API request handler, returning results only when complete.

**Why it fails:** Docling conversion of a large PDF can take 30-120 seconds. Embedding hundreds of chunks adds more time. HTTP connections time out, load balancers drop requests, and the API thread pool is exhausted -- blocking all other requests.

**Instead:** Return `202 Accepted` with a document ID immediately. Process asynchronously via the job queue. Clients poll `GET /v1/documents/{id}` for status, or use webhooks for completion notification.

```python
# WRONG: synchronous processing
@router.post("/v1/documents")
async def ingest(file: UploadFile):
    markdown = convert(file)         # 30-120s blocked
    chunks = chunk(markdown)         # 5-10s blocked
    vectors = embed(chunks)          # 10-30s blocked
    upsert_qdrant(vectors)           # 2-5s blocked
    return {"status": "complete"}    # Client likely already timed out

# CORRECT: async queue-based
@router.post("/v1/documents", status_code=202)
async def ingest(file: UploadFile):
    doc_id = await create_document(file)
    await enqueue_conversion(doc_id)
    return {"doc_id": doc_id, "status": "pending"}
```

### Anti-Pattern 2: Global Qdrant Collection Without Tenant Filtering

**What:** Storing all tenants' vectors in a single collection without any tenant isolation mechanism (no payload filter, no separate collections).

**Why it fails:** A search query for Tenant A returns chunks belonging to Tenant B. This is a data leak -- a security incident in any multi-tenant system. Even if you "always remember to filter," a single missed filter parameter exposes cross-tenant data.

**Instead:** Use collection-per-tenant (hard isolation) or payload-based tenancy with `is_tenant=True` (soft isolation with mandatory filter). Enforce the filter at the service layer so individual routes cannot skip it.

```python
# WRONG: no tenant isolation
results = qdrant.search(collection_name="documents", query_vector=vec, limit=10)

# CORRECT: tenant isolation enforced in service layer
class QdrantService:
    async def search(self, tenant_id: str, query_vector: list, limit: int):
        collection = f"tenant_{tenant_id}"  # hard isolation
        return await self.client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=limit,
        )
```

### Anti-Pattern 3: No Dead Letter / Failed Job Tracking

**What:** Letting failed jobs (after max retries) silently disappear from the Redis queue with no record of what failed or why.

**Why it fails:** Documents get stuck in "converting" or "chunking" status forever. Users see documents that never complete but get no error information. Operations teams cannot diagnose or retry failures. The system appears to silently lose documents.

**Instead:** On final retry failure, update the MongoDB document record with `status: failed` and the error message. Optionally maintain a `failed_jobs` collection in MongoDB as a dead letter store for post-mortem analysis.

```python
# workers/converter.py
async def convert_document(ctx: dict, doc_id: str, tenant_id: str):
    try:
        # ... conversion logic ...
        pass
    except Exception as e:
        job_try = ctx.get("job_try", 1)
        max_tries = ctx.get("max_tries", 3)

        if job_try < max_tries:
            raise Retry(defer=job_try * 15)  # exponential-ish backoff

        # Final failure: record in MongoDB for visibility
        await ctx["mongodb"].update_document(doc_id, {
            "status": "failed",
            "error": f"Conversion failed after {max_tries} attempts: {str(e)}",
            "updated_at": datetime.utcnow(),
        })

        # Optional: dead letter record for ops
        await ctx["mongodb"].insert_failed_job({
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "job_type": "convert",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "attempts": max_tries,
            "failed_at": datetime.utcnow(),
        })

        raise  # Let ARQ mark job as failed
```

---

## Integration Points

### External Services

| Service              | Protocol     | Auth                  | Failure Mode                          | Mitigation                                    |
|----------------------|--------------|-----------------------|---------------------------------------|-----------------------------------------------|
| Azure Blob Storage   | HTTPS REST   | Connection string     | Network timeout, throttling           | Retry with backoff, circuit breaker            |
| Azure OpenAI         | HTTPS REST   | API key + endpoint    | Rate limit (429), timeout, model down | Batch requests, exponential backoff, fallback model |
| Qdrant               | gRPC / HTTP  | API key (optional)    | Collection not found, OOM             | Health check, create-if-not-exists on startup  |
| MongoDB              | TCP (wire)   | Connection string     | Connection pool exhaustion, slow query| Connection pooling (Motor), index optimization |
| Redis                | TCP (RESP)   | Password (optional)   | Connection refused, memory full       | Connection retry, maxmemory-policy=allkeys-lru |

### Internal Boundaries

```
+------------------+     +-------------------+     +------------------+
|   api/ layer     |     |  services/ layer  |     |   db/ layer      |
|                  |     |                   |     |                  |
| Routes call      |---->| Pure business     |---->| Client wrappers  |
| service methods  |     | logic, no         |     | handle connection|
| with tenant_id   |     | framework deps    |     | pooling, retries |
+------------------+     +-------------------+     +------------------+
        |                         ^
        |                         |
+-------v--------+     +---------+---------+
| models/ layer  |     |  workers/ layer   |
|                |     |                   |
| Pydantic models|     | ARQ job handlers  |
| shared by all  |     | call services/    |
+----------------+     +-------------------+

Rules:
  - api/ imports from: models/, services/, db/
  - workers/ imports from: models/, services/, db/
  - services/ imports from: models/, db/
  - models/ imports from: nothing (leaf dependency)
  - db/ imports from: models/ (for type hints only)
  - api/ NEVER imports from workers/
  - workers/ NEVER imports from api/
```

---

## Sources

### Official Documentation
- [Qdrant Multitenancy Guide](https://qdrant.tech/documentation/guides/multitenancy/) -- Official guide on payload-based and tiered multitenancy patterns
- [Qdrant Multitenancy Article](https://qdrant.tech/articles/multitenancy/) -- Implementation details for custom sharding and tenant promotion
- [Qdrant 1.16 Release: Tiered Multitenancy](https://qdrant.tech/blog/qdrant-1.16.x/) -- Tiered multitenancy feature announcement
- [Qdrant Payload Indexing](https://qdrant.tech/documentation/concepts/indexing/) -- Payload index types and `is_tenant` configuration
- [Docling GitHub](https://github.com/docling-project/docling) -- Docling document conversion library
- [Docling Quickstart](https://docling-project.github.io/docling/getting_started/quickstart/) -- Getting started with DocumentConverter
- [Docling Document Converter Reference](https://docling-project.github.io/docling/reference/document_converter/) -- API reference for Docling
- [FastAPI Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/) -- Official guide on structuring larger FastAPI projects
- [ARQ Documentation](https://arq-docs.helpmanual.io/) -- Official ARQ async job queue docs
- [MongoDB RAG with Atlas Vector Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/rag/) -- Official MongoDB RAG integration docs

### Architecture and Patterns
- [Building Resilient Task Queues in FastAPI with ARQ Retries](https://davidmuraya.com/blog/fastapi-arq-retries/) -- ARQ retry patterns with exponential backoff code examples
- [Managing Background Tasks in FastAPI: BackgroundTasks vs ARQ + Redis](https://davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in/) -- Comparison of FastAPI background task approaches
- [FastAPI + ARQ GitHub Example](https://github.com/davidmuraya/fastapi-arq) -- Reference implementation of FastAPI with ARQ workers
- [Effective Practices for Architecting a RAG Pipeline (InfoQ)](https://www.infoq.com/articles/architecting-rag-pipeline/) -- Production RAG architecture patterns
- [Structuring a FastAPI Project: Best Practices](https://dev.to/mohammad222pr/structuring-a-fastapi-project-best-practices-53l6) -- Directory layout and separation of concerns
- [Vertical Monorepo Architecture for FastAPI](https://sqr-075.lsst.io/) -- Shared Pydantic models between API and workers in a monorepo
- [FastAPI Best Practices (zhanymkanov)](https://github.com/zhanymkanov/fastapi-best-practices) -- Community-curated FastAPI conventions

### RAG Pipeline Design
- [Building a Scalable Data Ingestion Pipeline for RAG Systems](https://medium.com/@tejpal.abhyuday/building-a-scalable-data-ingestion-pipeline-for-rag-systems-a-complete-guide-260c287395c5) -- Complete guide to RAG ingestion architecture (Jan 2026)
- [RAG Pipeline Deep Dive: Ingestion, Chunking, Embedding, and Vector Search](https://medium.com/@derrickryangiggs/rag-pipeline-deep-dive-ingestion-chunking-embedding-and-vector-search-abd3c8bfc177) -- Stage-by-stage pipeline walkthrough (Jan 2026)
- [Document Processing Pipelines: From Raw Files to Vector-Ready Chunks](https://dataa.dev/2024/09/15/document-processing-pipelines-from-raw-files-to-vector-ready-chunks/) -- Pipeline stage design and error handling
- [Document Ingestion Pipeline (DBOS)](https://docs.dbos.dev/python/examples/document-detective) -- Queue-based document processing with state recovery
- [RAG Data Ingestion: Enterprise Implementation (Informatica)](https://www.informatica.com/resources/articles/enterprise-rag-data-ingestion.html) -- Enterprise-scale ingestion patterns
- [Chunking Strategies for RAG (Weaviate)](https://weaviate.io/blog/chunking-strategies-for-rag) -- Comparison of fixed, recursive, and semantic chunking
- [Best Chunking Strategies for RAG 2026 (Firecrawl)](https://www.firecrawl.dev/blog/best-chunking-strategies-rag) -- Current benchmarks on chunking approaches

### Multi-Tenancy (Confidence: HIGH)
- [Multi-Tenancy With Qdrant Complete Guide](https://ai.gopubby.com/multi-tenancy-with-qdrant-complete-guide-ec66075f1efc) -- End-to-end implementation walkthrough
- [The Tao of Qdrant Multi-Tenancy](https://medium.com/qdrant/the-tao-of-qdrant-multi-tenancy-162c71f830fb) -- Qdrant team article on tenancy trade-offs (Sep 2025)
- [One Collection to Rule Them All](https://medium.com/@mohammedarbinsibi/one-collection-to-rule-them-all-efficient-multitenancy-in-qdrant-bda79712a4eb) -- Payload-based tenancy implementation

### Error Handling (Confidence: HIGH)
- [Dead Letter Queue Patterns for Failed Message Handling](https://oneuptime.com/blog/post/2026-02-09-dead-letter-queue-patterns/view) -- DLQ design patterns (Feb 2026)
- [Dead Letter Queues in Python](https://oneuptime.com/blog/post/2026-01-24-dead-letter-queues-python/view) -- Python implementation patterns (Jan 2026)

---

## Confidence Notes

- **HIGH confidence:** Queue-based pipeline architecture, ARQ retry patterns, Qdrant multitenancy approaches, MongoDB schema patterns, FastAPI project structure. All verified against official documentation and multiple independent sources.
- **HIGH confidence:** The collection-per-tenant Qdrant strategy in DocIngest's DESIGN.md is valid for the stated scale. Qdrant officially supports both approaches and recommends collection-per-tenant for hard isolation with moderate tenant counts.
- **MEDIUM confidence:** Specific chunking token sizes (512 tokens, 10-15% overlap) from DESIGN.md align with community benchmarks but optimal values are workload-dependent. Start with these defaults and tune based on retrieval quality metrics.
- **LOW confidence:** Reranker selection (cross-encoder vs Cohere vs Azure-hosted). DESIGN.md marks this as TBD. Performance depends heavily on domain and latency requirements. Recommend starting with a local cross-encoder for dev and benchmarking options before committing.
