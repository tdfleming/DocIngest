# Technology Stack Research — DocIngest

**Domain:** Document ingestion engine / RAG pipeline
**Date:** 2026-03-03
**Confidence Level:** HIGH (based on official docs, PyPI releases, and benchmarks published 2025-2026)
**Python Version:** 3.12+

---

## Recommended Stack

### Core Technologies

| Name | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| **FastAPI** | `>=0.115,<1` | REST API framework | Already in use. Pydantic v2 native, JSON serialization in Rust (2x perf), async-first. Dropped Pydantic v1 support. No reason to change. |
| **Docling** | `>=2.75,<3` | PDF/HTML/DOCX/PPTX conversion | Already in use. IBM open-source (MIT), runs locally on CPU, AI-powered layout analysis (DocLayNet + TableFormer), handles tables/headings/figures. Scored 9/10 in 2025 parser benchmarks. Has built-in chunking (HybridChunker). Active development under Linux Foundation AI & Data. Requires Python 3.10+. |
| **Qdrant** | Server: `>=1.13` / Client: `>=1.17,<2` | Vector database | Already in use. Native async Python client, built-in BM25 support (v1.17+), fastembed integration, gRPC support. Docker image readily available. |
| **MongoDB** | `>=7.0` | Document/metadata store | Already in use. Mature, well-suited for document metadata and job state. |
| **Redis** | `>=7.0` | Job broker / caching | Already in use. Required by ARQ. Lightweight, proven. |
| **ARQ** | `>=0.26,<1` | Async job queue | Already in use. Async-native, natural fit for FastAPI. **Note:** ARQ is in maintenance-only mode (v0.27.0 is latest). Adequate for this project's scale but consider Taskiq for future projects. |
| **MinIO** | Docker: `latest` / Python SDK: `>=7.2,<8` | Local blob storage (replaces Azure Blob) | S3-compatible API. Drop-in replacement for Azure Blob Storage in local/Docker environments. Lightweight Docker image, works on minimal hardware. Python SDK (`minio>=7.2.20`) requires Python 3.10+. |
| **FastEmbed** | `>=0.7,<1` | Local embeddings (replaces Azure OpenAI) | Built by Qdrant team. Uses ONNX Runtime (no PyTorch dependency). Lightweight, CPU-optimized. Native integration with qdrant-client v1.17+. Default model: BAAI/bge-small-en-v1.5 (384 dims). Supports quantized models. |

### Supporting Libraries

| Name | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| **PyMongo (async)** | `>=4.10,<5` | MongoDB async driver (replaces Motor) | Motor is deprecated as of May 2025 in favor of PyMongo's native async API (`AsyncMongoClient`). Better latency/throughput — no thread pool. Direct asyncio support. Migration is straightforward: swap `MotorClient` for `AsyncMongoClient`. |
| **Beanie** | `>=2.0,<3` | MongoDB ODM | Pydantic-based async ODM for MongoDB. v2.0 migrated from Motor to PyMongo Async. Provides type-safe document models, validation, migrations. Excellent FastAPI integration. |
| **Pydantic** | `>=2.10,<3` | Data validation / settings | Already in use. v2 is Rust-powered, much faster. Required by FastAPI and Beanie. |
| **Pydantic-Settings** | `>=2.7,<3` | Configuration management | Already in use. Environment variable parsing with type validation. |
| **structlog** | `>=24.4,<25` | Structured logging | Already in use. JSON-formatted structured logs. |
| **httpx** | `>=0.28,<1` | HTTP client | Already in use. Async-capable HTTP client for URL ingestion. |
| **python-multipart** | `>=0.0.18,<1` | Multipart form parsing | Already in use. Required by FastAPI for file uploads. |
| **uvicorn** | `>=0.34,<1` | ASGI server | Already in use. Standard production server for FastAPI. |

### Development Tools

| Name | Version | Purpose | Why Recommended |
|------|---------|---------|-----------------|
| **pytest** | `>=8.3,<9` | Test framework | Already in use. Standard Python test framework. |
| **pytest-asyncio** | `>=0.25,<1` | Async test support | Already in use. Required for testing async FastAPI/ARQ code. |
| **ruff** | `>=0.9,<1` | Linter + formatter | Already in use. Extremely fast, replaces flake8+isort+black. |
| **hatchling** | latest | Build backend | Already in use. Modern Python build backend. |

---

## Installation Commands

### Updated pyproject.toml dependencies

```toml
[project]
dependencies = [
    # API
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.34,<1",
    "python-multipart>=0.0.18,<1",

    # Document conversion + chunking
    "docling>=2.75,<3",

    # Embeddings (local, replaces Azure OpenAI)
    "fastembed>=0.7,<1",

    # Databases
    "pymongo>=4.10,<5",
    "beanie>=2.0,<3",
    "qdrant-client>=1.17,<2",
    "redis>=5.2,<6",

    # Job queue
    "arq>=0.26,<1",

    # Blob storage (local, replaces Azure Blob)
    "minio>=7.2,<8",

    # Utilities
    "pydantic>=2.10,<3",
    "pydantic-settings>=2.7,<3",
    "httpx>=0.28,<1",
    "structlog>=24.4,<25",
]
```

### Docker Compose services to add

```yaml
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"   # S3 API
      - "9001:9001"   # Web console
    volumes:
      - minio_data:/data
```

### Key environment variable changes

```bash
# REMOVE these Azure dependencies:
# AZURE_BLOB_CONNECTION_STRING
# AZURE_OPENAI_ENDPOINT
# AZURE_OPENAI_API_KEY
# AZURE_OPENAI_EMBEDDING_DEPLOYMENT

# ADD these local alternatives:
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET_PREFIX=tenant-

EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
```

---

## Alternatives Considered

| Component | Alternative | Why Not Chosen |
|-----------|------------|----------------|
| **Doc Conversion** | Unstructured.io | Quality has reportedly declined in 2025. More complex setup. Docling is already integrated and scores 9/10 in benchmarks. |
| **Doc Conversion** | PyMuPDF | Fast for raw text extraction but lacks AI-powered layout understanding, table structure recognition, and multi-format support that Docling provides. Better as a supplement, not replacement. |
| **Doc Conversion** | LlamaParse | Cloud-only API (no local deployment). Highest rated (10/10) but adds external dependency and cost. Conflicts with local-first constraint. |
| **Chunking** | LangChain RecursiveCharacterTextSplitter | Generic text splitting without document structure awareness. Docling's HybridChunker is structure-aware and uses the parsed document hierarchy. No need for a separate chunking library. |
| **Chunking** | semantic-text-splitter (Rust+Python) | Fast (Rust-backed) but operates on plain text, not structured documents. Docling's HybridChunker already handles tokenization-aware splitting on top of hierarchical structure. |
| **Chunking** | LlamaIndex SentenceSplitter | Currently in pyproject.toml (`llama-index-core`). Adds heavy dependency tree. Docling's built-in HybridChunker eliminates need for LlamaIndex entirely. |
| **Embeddings** | sentence-transformers (v5.2.3) | More mature ecosystem, larger model selection. But requires PyTorch (~2GB dependency). FastEmbed uses ONNX Runtime (~50MB), much lighter for containerized deployment. |
| **Embeddings** | Ollama | Requires running a separate inference server. FastEmbed runs in-process with ONNX. Simpler deployment for this use case. |
| **Embedding Model** | BAAI/bge-m3 | Multilingual, higher MTEB score (63.0). But 1024 dimensions, slower, larger. bge-small-en-v1.5 is sufficient for English-primary use cases and much faster. Upgrade path is easy if needed. |
| **Embedding Model** | all-MiniLM-L6-v2 | Popular and fast (384 dims). But bge-small-en-v1.5 scores higher on MTEB benchmarks and is FastEmbed's default. |
| **Job Queue** | Celery | Battle-tested but synchronous by design. Requires extra config for async. Heavy dependency (kombu, billiard, vine). ARQ is async-native and already integrated. |
| **Job Queue** | Taskiq | Modern async-first, faster than ARQ in benchmarks, multi-broker support (Redis, NATS, Kafka). Worth considering if ARQ's maintenance-only status becomes a problem. Not chosen because ARQ is already working. |
| **MongoDB Driver** | Motor (v3.7.1) | **Deprecated** as of May 2025. PyMongo Async API is the official replacement with better performance. Motor receives only bug fixes until May 2026, then critical fixes only until May 2027. Must migrate. |
| **MongoDB ODM** | ODMantic | Also async + Pydantic, but Beanie has larger community, better documentation, and v2.0 already migrated to PyMongo Async. |
| **MongoDB ODM** | Raw PyMongo | No ODM. Works but loses Pydantic model validation, migration support, and clean query syntax that Beanie provides. |
| **Blob Storage** | Local filesystem | Simplest option, but no S3-compatible API, no web console, no bucket policies. MinIO provides a proper object storage abstraction that maps cleanly to Azure Blob concepts (containers = buckets). |
| **Blob Storage** | Ceph / Garage | Overkill for local development. MinIO is lighter and simpler to deploy in Docker. |
| **Vector DB** | Weaviate / Milvus / ChromaDB | Qdrant is already integrated, has excellent Python async support, and the team builds FastEmbed. Tight ecosystem integration. No reason to switch. |

---

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| **Motor** | Deprecated May 2025. Replace with `pymongo.AsyncMongoClient`. No new features; only bug fixes until 2026, critical only until 2027. |
| **llama-index-core** | Currently in pyproject.toml. Heavy dependency (~50+ transitive packages). Only used for chunking, which Docling's HybridChunker handles natively. Remove entirely. |
| **llama-index-embeddings-azure-openai** | Currently in pyproject.toml. Azure dependency being eliminated. FastEmbed replaces this. Remove entirely. |
| **azure-storage-blob** | Currently in pyproject.toml. Replaced by MinIO with S3-compatible API. Remove entirely. |
| **openai** (Python SDK for Azure OpenAI) | Currently in pyproject.toml. No longer needed — FastEmbed handles local embeddings. Remove entirely. |
| **LangChain** | Massive dependency, high abstraction overhead. All needed functionality (conversion, chunking, embedding, vector ops) is covered by Docling + FastEmbed + qdrant-client directly. |
| **PyTorch** (as direct dependency) | FastEmbed uses ONNX Runtime instead. Saves ~2GB in container images. Only add PyTorch if you need GPU-accelerated embedding with sentence-transformers. |
| **Pydantic v1** | FastAPI has dropped Pydantic v1 support. Ensure all models use Pydantic v2 syntax. |

---

## Version Compatibility Notes

### Python 3.12+ Compatibility Matrix

| Package | Python 3.12 | Python 3.13 | Notes |
|---------|-------------|-------------|-------|
| FastAPI >=0.115 | Yes | Yes | Dropped Python 3.8 support |
| Docling >=2.70 | Yes | Verify | Dropped Python 3.9 in v2.70.0, requires 3.10+ |
| fastembed >=0.7 | Yes | Verify | Uses onnxruntime which supports 3.12 |
| qdrant-client >=1.17 | Yes | Yes | |
| pymongo >=4.10 | Yes | Yes | AsyncMongoClient is GA |
| beanie >=2.0 | Yes | Verify | Uses PyMongo Async (not Motor) |
| minio >=7.2 | Yes | Verify | Requires Python 3.10+ |
| arq >=0.26 | Yes | Yes | |
| onnxruntime >=1.24 | Yes | Verify | CPython 3.12 wheels available |

### Qdrant Version Alignment

| Qdrant Server | qdrant-client | Notes |
|---------------|---------------|-------|
| v1.13.x | >=1.13,<2 | Current pyproject.toml pin |
| v1.17.x | >=1.17,<2 | Recommended: adds built-in BM25, native fastembed |

### Breaking Changes to Watch

1. **Motor -> PyMongo Async**: `MotorClient` becomes `AsyncMongoClient`. `to_list(0)` becomes `to_list(None)`. No `io_loop` parameter.
2. **Beanie 2.0**: Internal field renames (`motor_db` -> `pymongo_db`, `motor_collection` -> `pymongo_collection`). Removed `multiprocessing_mode` from init.
3. **Docling HybridChunker**: Available since docling-core 2.8.0. Requires specifying a tokenizer aligned to embedding model.
4. **FastEmbed default model**: BAAI/bge-small-en-v1.5 produces 384-dim vectors (not 1536). Qdrant collection config must be updated.
5. **Qdrant vector dimensions**: Changing from Azure OpenAI 1536-dim to FastEmbed 384-dim requires recreating collections or creating new ones.

---

## Key Architecture Decisions

### 1. Docling's Built-in Chunking Replaces LlamaIndex

Docling provides two chunkers that eliminate the need for LlamaIndex:

- **HierarchicalChunker**: One chunk per document element (paragraph, table, list). Preserves heading hierarchy.
- **HybridChunker**: Builds on HierarchicalChunker, adds tokenization-aware splitting (splits oversized chunks) and merging (combines undersized chunks within same section). Aligns with the DESIGN.md two-pass approach.

**Pattern:**
```python
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert(source)
doc = result.document

chunker = HybridChunker(
    tokenizer="BAAI/bge-small-en-v1.5",  # Align to embedding model
    max_tokens=512,
    merge_peers=True,
)
chunks = list(chunker.chunk(doc))
```

### 2. FastEmbed for In-Process Embeddings

FastEmbed runs ONNX models in-process — no separate inference server needed:

```python
from fastembed import TextEmbedding

model = TextEmbedding("BAAI/bge-small-en-v1.5")
embeddings = list(model.embed(["chunk text 1", "chunk text 2"]))
# Each embedding is a numpy array of shape (384,)
```

Or use qdrant-client's built-in fastembed integration:

```python
from qdrant_client import AsyncQdrantClient

client = AsyncQdrantClient("localhost", port=6333)
await client.add(
    collection_name="tenant_abc",
    documents=["chunk text 1", "chunk text 2"],
    metadata=[{"doc_id": "123"}, {"doc_id": "123"}],
)
```

### 3. MinIO as Azure Blob Replacement

MinIO provides S3-compatible API, making the storage abstraction clean:

```python
from minio import Minio

client = Minio(
    "minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

# Create tenant bucket (replaces Azure container)
client.make_bucket(f"tenant-{tenant_id}")

# Upload file (replaces Azure blob upload)
client.put_object(
    f"tenant-{tenant_id}",
    f"raw/{doc_id}.pdf",
    file_data,
    length=file_size,
    content_type="application/pdf",
)
```

### 4. PyMongo Async Replaces Motor

```python
# OLD (Motor - deprecated)
from motor.motor_asyncio import AsyncIOMotorClient
client = AsyncIOMotorClient("mongodb://localhost:27017")

# NEW (PyMongo Async)
from pymongo import AsyncMongoClient
client = AsyncMongoClient("mongodb://localhost:27017")
```

### 5. FastAPI File Upload Best Practices

For large documents, use streaming to avoid memory spikes:

```python
from fastapi import UploadFile

@app.post("/v1/documents")
async def upload_document(file: UploadFile):
    # Stream to MinIO in chunks — never load entire file into memory
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    async with aiofiles.open(temp_path, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            await f.write(chunk)
    # Then upload to MinIO from temp file
```

---

## Sources

### HIGH Confidence (Official docs, PyPI, GitHub releases)

- [Docling Official Documentation](https://docling-project.github.io/docling/) — chunking, conversion, quickstart
- [Docling PyPI](https://pypi.org/project/docling/) — v2.75.0, Python 3.10+ requirement
- [Docling GitHub](https://github.com/docling-project/docling) — MIT license, IBM Research
- [Docling Chunking Concepts](https://docling-project.github.io/docling/concepts/chunking/) — HierarchicalChunker and HybridChunker documentation
- [Docling Hybrid Chunking Example](https://docling-project.github.io/docling/examples/hybrid_chunking/) — usage patterns
- [Qdrant Python Client Docs](https://python-client.qdrant.tech/) — v1.17.0, async API
- [qdrant-client PyPI](https://pypi.org/project/qdrant-client/) — v1.17.0, Feb 2026
- [Qdrant Async API Tutorial](https://qdrant.tech/documentation/tutorials-develop/async-api/) — AsyncQdrantClient usage
- [FastEmbed GitHub](https://github.com/qdrant/fastembed) — ONNX-based, lightweight
- [fastembed PyPI](https://pypi.org/project/fastembed/) — v0.7.1
- [Motor Deprecation Notice](https://www.mongodb.com/docs/drivers/motor/) — deprecated May 2025
- [PyMongo Async Migration Guide](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/) — Motor to AsyncMongoClient
- [Beanie ODM GitHub](https://github.com/BeanieODM/beanie) — v2.0 with PyMongo Async
- [MinIO Python SDK GitHub](https://github.com/minio/minio-py) — v7.2.20
- [minio PyPI](https://pypi.org/project/minio/) — Python 3.10+ requirement
- [sentence-transformers PyPI](https://pypi.org/project/sentence-transformers/) — v5.2.3
- [ARQ GitHub](https://github.com/python-arq/arq) — v0.27.0, maintenance mode
- [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/) — Pydantic v2 only
- [FastAPI File Uploads Docs](https://fastapi.tiangolo.com/tutorial/request-files/) — UploadFile best practices
- [semantic-text-splitter PyPI](https://pypi.org/project/semantic-text-splitter/) — v0.29.0

### MEDIUM Confidence (Benchmarks, comparisons, technical blog posts)

- [Docling arXiv Paper](https://arxiv.org/html/2501.17887v1) — efficiency benchmarks, 3.1 sec/page on CPU
- [PDF Parsers Comparative Study](https://arxiv.org/html/2410.09871v1) — multi-parser benchmark
- [PDF Parsers Ranked 2025](https://infinityai.medium.com/3-proven-techniques-to-accurately-parse-your-pdfs-2c01c5badb84) — Docling 9/10, LlamaParse 10/10
- [Best Embedding Models 2025 MTEB](https://app.ailog.fr/en/blog/guides/choosing-embedding-models) — BGE-M3 63.0, model comparison
- [13 Best Embedding Models 2026](https://elephas.app/blog/best-embedding-models) — comprehensive comparison
- [FastEmbed vs Sentence Transformers](https://newmind.ai/en/blog/comparing-fastembed-and-sentence-transformers-a-comprehensive-guide-to-text-embedding-libraries) — tradeoffs analysis
- [Chunking Strategies for RAG 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag) — 512 tokens, 10-20% overlap
- [Document Chunking 70% Accuracy Boost](https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide) — recursive 512-token wins benchmark
- [ARQ vs Celery for FastAPI](https://www.bithost.in/blog/tech-3/how-to-run-fastapi-background-tasks-arq-vs-celery-11) — async comparison
- [FastAPI Background Tasks vs Celery vs ARQ](https://medium.com/@komalbaparmar007/fastapi-background-tasks-vs-celery-vs-arq-picking-the-right-asynchronous-workhorse-b6e0478ecf4a) — decision framework
- [Taskiq vs ARQ](https://chris48s.github.io/blogmarks/posts/2024/arq-taskiq/) — architectural differences
- [Python Task Queue Benchmark](https://stevenyue.com/blogs/exploring-python-task-queue-libraries-with-load-test) — Taskiq 10x faster than ARQ in load tests
- [MinIO as Azure Blob Alternative](https://openalternative.co/alternatives/azure-blob-storage) — S3-compatible, lightweight
- [Beanie vs ODMantic](https://medium.com/@saveriomazza/beanie-vs-odmantic-best-mongodb-odm-for-fastapi-5f694cb63258) — Beanie preferred for FastAPI

### LOW Confidence (Unverified claims, older posts)

- [FastEmbed slower than SentenceTransformers on M2 Max](https://github.com/qdrant/fastembed/issues/535) — hardware-specific, may not apply to x86/Docker
- [FastEmbed slower for all-MiniLM-L6-v2](https://github.com/qdrant/fastembed/issues/292) — model-specific performance issue
- [Unstructured.io quality decline](https://infinityai.medium.com/3-proven-techniques-to-accurately-parse-your-pdfs-2c01c5badb84) — single reviewer's assessment, not independently verified

---

## Summary of Changes from Current pyproject.toml

| Action | Package | Rationale |
|--------|---------|-----------|
| **KEEP** | fastapi, uvicorn, python-multipart | No changes needed |
| **KEEP** | docling | Upgrade pin from `>=2.14` to `>=2.75` for HybridChunker + latest fixes |
| **KEEP** | qdrant-client | Upgrade pin from `>=1.13` to `>=1.17` for built-in BM25 and fastembed |
| **KEEP** | redis | No changes needed |
| **KEEP** | arq | No changes needed; monitor maintenance-only status |
| **KEEP** | pydantic, pydantic-settings, httpx, structlog | No changes needed |
| **ADD** | fastembed>=0.7,<1 | Local embeddings, replaces Azure OpenAI |
| **ADD** | pymongo>=4.10,<5 | Async MongoDB driver, replaces Motor |
| **ADD** | beanie>=2.0,<3 | MongoDB ODM with Pydantic integration |
| **ADD** | minio>=7.2,<8 | Local blob storage, replaces Azure Blob |
| **REMOVE** | motor>=3.7,<4 | Deprecated; replaced by pymongo async |
| **REMOVE** | llama-index-core>=0.12,<1 | Replaced by Docling's built-in HybridChunker |
| **REMOVE** | llama-index-embeddings-azure-openai>=0.3,<1 | Replaced by fastembed |
| **REMOVE** | azure-storage-blob>=12.24,<13 | Replaced by minio |
| **REMOVE** | openai>=1.60,<2 | No longer needed without Azure OpenAI |
