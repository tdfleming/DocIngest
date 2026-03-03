# Common Pitfalls: Document Ingestion Engine / RAG Pipeline

- **Domain:** Multi-tenant document ingestion engine with RAG pipeline
- **Date:** 2026-03-03
- **Confidence:** HIGH (sourced from post-mortems, production experience reports, and vendor documentation)
- **Stack Context:** FastAPI, ARQ+Redis, MongoDB, Qdrant, Docling, Python 3.12+, Docker

---

## Critical Pitfalls

### 1. Chunking That Destroys Semantic Coherence

**What goes wrong:** Fixed-size or naive chunking splits documents mid-sentence, mid-table, or mid-paragraph, producing fragments that embed poorly and retrieve incoherently. A 2025 CDC policy RAG study found naive fixed-size chunking scored 0.47-0.51 faithfulness vs. 0.79-0.82 for optimized semantic chunking. 80% of RAG failures trace back to chunking decisions, not retrieval or generation.

**Why it happens:** Teams default to fixed token-count chunking because it is simple. They treat chunking as a solved problem and spend their optimization budget on model selection instead. Chunk size is often chosen arbitrarily (e.g., 512 tokens) without testing against actual query patterns.

**How to avoid:**
- Use structure-aware chunking that respects document hierarchy (headings, paragraphs, tables, lists).
- Implement overlap windows (10-20% of chunk size) to preserve context at boundaries.
- Test chunking quality with real queries before optimizing anything else -- chunking quality constrains retrieval accuracy more than embedding model choice.
- Preserve metadata (source document, section heading, page number) with each chunk for attribution.
- Handle tables and code blocks as atomic units; never split them mid-row or mid-block.

**Warning signs:** Retrieval returns partial sentences, table fragments, or context that starts mid-thought. Users report answers that "almost" answer their question but miss key details.

**Phase to address:** Design phase, before any embedding or search work begins.

---

### 2. Embedding Model Lock-In and Silent Migration Breakage

**What goes wrong:** The embedding model becomes a hidden dependency that, when changed, silently corrupts the entire vector store. Even small tweaks to embedding models (adjusting dimensions, switching providers) break applications because embeddings from different models occupy incompatible geometric spaces. L2 normalization and standardization do NOT make different model spaces compatible -- semantically similar items cluster differently, and nearest neighbors in one space are not neighbors in another.

**Why it happens:** Teams treat embedding models as interchangeable and do not version them. Proprietary model providers deprecate models without warning (e.g., OpenAI deprecated text-embedding-ada-002). Teams discover too late that upgrading requires full re-indexing of potentially millions of documents.

**How to avoid:**
- Store the embedding model identifier and version alongside every vector in metadata.
- Design schema to support parallel collections/indexes for migration (old model + new model running simultaneously).
- Prefer open-source local models (e.g., Nomic, BGE, sentence-transformers) so you control the model binary and can always regenerate vectors.
- Build re-indexing as a first-class pipeline operation, not an afterthought.
- Never mix embeddings from different models in the same collection.
- Always validate that query-time embedding model matches index-time embedding model.

**Warning signs:** Retrieval quality degrades after a library update. Cosine similarity scores shift without any data changes. Dimension mismatch errors appear in logs.

**Phase to address:** Architecture phase. Must be planned before first vector is stored.

---

### 3. Multi-Tenant Data Leakage Through Missing Tenant Filters

**What goes wrong:** A single missing `WHERE tenant_id = ?` clause, an unscoped cache key, or a background job without tenant context causes one tenant's documents to appear in another tenant's search results. In vector search, this is especially dangerous because payload-filter-based multi-tenancy (Qdrant's recommended approach) relies on the application always including the filter -- there is no database-level enforcement.

**Why it happens:** Multi-tenancy is bolted on after initial development. Tenant context is passed through HTTP headers but dropped in background workers, cache operations, or internal service calls. Developers test with a single tenant and never verify isolation. Qdrant's payload-based filtering is application-enforced, not database-enforced.

**How to avoid:**
- Propagate tenant_id through every layer: API -> job queue -> worker -> database -> cache -> vector store.
- Include tenant_id in ALL cache keys (Redis), ALL MongoDB queries, and ALL Qdrant search filters.
- Create payload indexes on tenant_id in Qdrant immediately after collection creation (critical for performance and correctness).
- Write integration tests that specifically verify cross-tenant isolation: ingest as tenant A, search as tenant B, assert zero results.
- Consider Row-Level Security (RLS) in MongoDB or database-level isolation for high-security tenants.
- Log and alert on any query that does not include a tenant filter.

**Warning signs:** Integration tests only use a single tenant. No explicit tenant-isolation test exists. Background workers receive job payloads without tenant_id. Cache keys do not include tenant identifiers.

**Phase to address:** Architecture phase. Must be designed from day one, not retrofitted.

---

### 4. Docling Conversion Failures on Real-World Documents

**What goes wrong:** Docling hangs indefinitely on certain PDFs, produces garbled output from scanned documents, destroys complex table structures, and silently fails on documents with non-standard encodings. Enterprise documents are messy -- scanned contracts, handwritten annotations, complex financial tables, legacy PDFs with missing font mappings -- and Docling's OCR capabilities are limited for these cases.

**Why it happens:** Development and testing use clean, well-formed documents. Production receives user-uploaded files that are corrupted, password-protected, scanned images, or created by dozens of different PDF generators with varying compliance levels. Docling downloads and runs AI models from Hugging Face, adding latency and resource pressure that is not visible in small-scale testing.

**How to avoid:**
- Implement hard timeouts on Docling conversion calls (it can hang indefinitely; documented in GitHub issue #2109).
- Run conversion in isolated worker processes that can be killed without affecting the main pipeline.
- Build a fallback chain: try Docling first, fall back to simpler extraction (e.g., PyPDF2/pdfplumber for text-only), and always report partial extraction vs. silent failure.
- Validate conversion output: check for empty results, garbled text (high ratio of non-printable characters), and suspiciously short output.
- Set memory limits on worker containers; Docling's AI models consume significant RAM.
- Handle tables as a special case; Docling assumes simple table structures and fails on varying column spans and merged cells.

**Warning signs:** Conversion jobs that "never finish." Workers consuming 4+ GB RAM. Output that is empty or contains Unicode replacement characters. Tables that come out as unstructured text.

**Phase to address:** Implementation phase. Build the fallback chain early; do not assume Docling handles everything.

---

### 5. Vector Collection Design That Breaks at Scale

**What goes wrong:** Creating separate Qdrant collections per tenant exhausts cluster resources. Missing payload indexes cause queries to use full-scan instead of indexed lookup, making filtered searches orders of magnitude slower. Payload schemas become inconsistent across ingestion pipelines, causing filters to silently return no results.

**Why it happens:** Developers create one-collection-per-tenant because it feels like proper isolation, not realizing Qdrant is optimized for single-collection multi-tenancy with payload filters. Payload indexes are forgotten or created after data is already loaded (which blocks updates and misses HNSW optimization). Field types are not enforced, so a `page_number` field is sometimes a string and sometimes an integer.

**How to avoid:**
- Use a single Qdrant collection with payload-based multi-tenancy for most cases. Qdrant documentation explicitly warns against per-tenant collections.
- Create ALL payload indexes immediately after collection creation, before any data insertion. This is critical: HNSW graphs only benefit from extra edges when generated after payload index creation.
- Use strict payload schemas: enforce types at the application layer before upserting.
- Index the `tenant_id` field as a keyword index (not full-text) for fast filtering.
- Consider Qdrant 1.16+'s Tiered Multitenancy for mixed tenant sizes.
- Monitor search latency per tenant; a sudden spike indicates missing indexes or cardinality estimation failures.

**Warning signs:** Search latency increases linearly with data volume. Qdrant logs show "full scan" in query plans. Cluster resource exhaustion with relatively few tenants. Filtered queries return unexpected empty results.

**Phase to address:** Architecture phase for collection design; implementation phase for index creation.

---

### 6. FastAPI/Worker Memory Growth Leading to OOM Kills

**What goes wrong:** FastAPI workers processing large documents see RSS memory climb continuously -- past 200MB, 300MB, 400MB, linearly beyond 2GB -- until containers are OOM-killed. The memory is not leaked in the traditional sense; it is fragmented. In async FastAPI applications, allocations from concurrent requests get interleaved across memory spans. When one request finishes, other requests still have objects in those same spans, keeping entire spans resident.

**Why it happens:** Python's default memory allocator (pymalloc/glibc malloc) handles fragmentation poorly under concurrent async workloads. Large document processing creates many temporary allocations that fragment the heap. Docker container memory limits are set based on steady-state, not peak processing of large files.

**How to avoid:**
- Use jemalloc as the memory allocator in Docker containers (LD_PRELOAD trick). This is a proven fix for FastAPI memory fragmentation.
- Process large documents in dedicated worker processes (ARQ workers), not in the API process.
- Set explicit memory limits on worker containers and configure ARQ's `max_jobs` to limit concurrency.
- Implement document size limits at upload time and reject files above the threshold.
- Monitor RSS memory over time; steady upward trends indicate fragmentation even if no leak exists.
- Consider worker recycling: restart worker processes after N jobs or when RSS exceeds a threshold.

**Warning signs:** Container restarts in production logs. RSS memory that only grows, never shrinks. OOM kills that correlate with large document uploads. Workers becoming unresponsive during processing.

**Phase to address:** Implementation phase for worker architecture; operations phase for memory monitoring and tuning.

---

### 7. Retrieval That Silently Returns Wrong Results

**What goes wrong:** The RAG pipeline returns confident-sounding answers based on irrelevant retrieved chunks. 70% of RAG failures happen before the LLM is ever called -- in retrieval and context assembly. A system with 95% accuracy per layer becomes only 81% reliable with 4 layers compounding errors. Users cannot distinguish between answers grounded in correct retrieval and answers grounded in wrong-but-plausible chunks.

**Why it happens:** Teams rely solely on vector similarity without hybrid search (BM25 + vectors). They skip reranking or apply it incorrectly (reranking the top 10 when the relevant document is at position 50). Evaluation uses synthetic queries that do not reflect real user behavior. No retrieval-quality monitoring exists in production.

**How to avoid:**
- Implement hybrid search: BM25 for keyword precision + vector search for semantic recall, then rerank.
- Measure recall@K before adding a reranker; a reranker cannot fix what was not retrieved.
- Normalize BM25 and vector scores properly before combining; they live on different scales.
- Log retrieved chunks alongside generated answers for debugging.
- Set similarity score thresholds; return "I don't know" when confidence is low rather than hallucinating.
- Build evaluation datasets from real user queries, not synthetic ones.

**Warning signs:** Users report answers that are "close but wrong." No retrieval quality metrics exist. Similarity scores are not logged or monitored. All answers appear confident regardless of retrieval quality.

**Phase to address:** Design phase for hybrid search architecture; testing phase for evaluation datasets.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-Term Cost | When Acceptable |
|----------|------------------|----------------|-----------------|
| Fixed-size chunking with no overlap | Fast to implement, predictable chunk count | Poor retrieval quality, broken context, 50% lower faithfulness scores | Prototype/PoC only; never production |
| Single embedding model hardcoded everywhere | No abstraction layer needed | Full re-index required on any model change; vendor lock-in | If using a stable open-source model you control |
| Per-tenant Qdrant collections | Simple mental model for isolation | Resource exhaustion at 50+ tenants, operational nightmare | Only if you have <5 tenants with very different schemas |
| No payload indexes on Qdrant | Faster initial data loading | Query performance degrades to full-scan at scale | Never acceptable; create indexes before data insertion |
| Synchronous document conversion in API handler | Simple request-response flow | API timeouts on large documents, blocked event loop, poor UX | Only for very small documents (<10 pages) in dev |
| No conversion timeout/fallback | Simpler error handling | Stuck workers, pipeline stalls, user-visible hangs | Never acceptable in production |
| pymalloc default allocator | No configuration needed | Memory fragmentation under concurrent load, OOM kills | Acceptable for low-concurrency dev environments |
| Manual spot-check evaluation | Quick to do, feels productive | Silent quality regressions go undetected, false confidence | Only during early prototyping |
| Tenant context via global variable/thread-local | Easy to access anywhere | Breaks in async code, causes data leakage in concurrent requests | Never acceptable with async frameworks like FastAPI |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|---------------|------------------|
| Qdrant payload filters | Not creating payload indexes; Qdrant silently falls back to slow full-scan | Create all payload indexes immediately after collection creation, before any data insertion |
| Qdrant + tenant isolation | Relying solely on application-level filter inclusion | Add middleware/decorator that injects tenant filter into every Qdrant query; write isolation tests |
| ARQ + Redis job queue | No timeout on conversion jobs; timed-out jobs cannot be retried (ARQ issue #401) | Set explicit `job_timeout`, implement idempotent retry logic, handle `TimeoutError` as terminal and re-enqueue |
| ARQ job results | Results expire silently (default 1 day) | Configure `expires_extra_ms` appropriately; do not rely on job results for critical state |
| MongoDB + tenant data | Missing tenant_id in queries, especially in aggregation pipelines | Use a query builder or repository pattern that always injects tenant_id; never raw queries |
| Redis cache + multi-tenancy | Cache keys without tenant prefix | Template: `{tenant_id}:{resource_type}:{resource_id}` for all cache keys |
| Docling + large PDFs | No timeout; Docling hangs indefinitely on malformed PDFs | Wrap in `asyncio.wait_for()` or process-level timeout; implement fallback extraction |
| Docling + complex tables | Assuming table output preserves structure | Post-process table output; validate row/column counts; consider specialized table extraction |
| FastAPI + file uploads | Processing uploads in the API handler (blocking event loop) | Accept upload, store to temp storage, enqueue background job, return job ID |
| Embedding API + batching | Sending one document at a time to embedding model | Batch embeddings (32-128 items per call); use async batching for throughput |
| Docker + Qdrant on Windows/WSL | Bind-mounting Windows folders into Qdrant container | Use Docker volumes instead of bind mounts; Windows hypervisor shared mounts are not fully POSIX-compatible |
| Docker + Qdrant startup | Assuming Qdrant is ready immediately after container starts | Implement health-check polling; Qdrant with large collections can take minutes to start; all APIs are unreachable during loading |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No payload index on tenant_id in Qdrant | Search latency grows linearly with total vector count | Create keyword index on tenant_id before inserting data | At 100K+ vectors across all tenants |
| Embedding one document at a time | Ingestion throughput plateaus; GPU/API underutilized | Batch embedding calls (32-128 items); parallelize across workers | At 1000+ documents/day ingestion rate |
| Oversized chunks (2000+ tokens) | High embedding latency; diluted vector representations; poor precision | Use 256-512 token chunks with 10-20% overlap | When query specificity matters (most production cases) |
| Undersized chunks (<100 tokens) | Fragmented context; high storage cost; more vectors to search | Merge related small chunks; use parent-child chunk hierarchies | When users ask complex multi-fact questions |
| Synchronous re-indexing | API unresponsive during re-index; user-facing latency spikes | Run re-indexing as background pipeline; use blue-green collection switching | At first large-scale re-index (model upgrade, schema change) |
| Single Qdrant collection without sharding config | Write throughput bottleneck; single-node limitation | Configure write-ahead-log and shard count for expected write volume | At 1M+ vectors with concurrent ingestion |
| Full document re-processing on metadata update | Unnecessary embedding API costs; slow updates | Separate metadata updates from content re-embedding; update Qdrant payload without re-vectorizing | When metadata changes are frequent (tags, permissions) |
| Not using connection pooling for MongoDB | Connection exhaustion under load; "too many open connections" errors | Use Motor async driver with explicit pool size; share client across workers | At 50+ concurrent requests |
| Redis as primary state store for job status | Redis eviction policies can silently delete job state | Use MongoDB for durable job state; Redis only for queue and cache | When Redis memory pressure increases |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Tenant_id derived from user input without validation | Tenant spoofing; access to other tenants' documents | Extract tenant_id from authenticated JWT claims only; never from query params or headers |
| No tenant filter in background workers | Cross-tenant data leakage in async processing | Pass tenant_id in every job payload; validate before processing; log tenant context |
| Qdrant API exposed without authentication | Anyone with network access can read/modify all vectors | Enable Qdrant API key authentication; use network policies to restrict access to API servers only |
| Uploaded files stored with predictable paths | Path traversal; unauthorized file access | Use random UUIDs for storage paths; validate file paths; never use user-supplied filenames |
| No document size/type validation | Zip bombs; malicious PDFs; resource exhaustion | Validate file type (magic bytes, not just extension); enforce size limits; scan for known exploits |
| Embedding vectors expose document content | Embedding inversion attacks can reconstruct approximate text | Evaluate risk for sensitive data; consider encryption at rest; restrict vector API access |
| Shared encryption keys across tenants | Breach of one tenant's key exposes all tenants | Per-tenant encryption keys for high-security deployments |
| No audit logging of document access | Cannot detect or investigate data breaches | Log all document access with tenant_id, user_id, timestamp, action |
| ARQ Redis instance shared without AUTH | Any process on the network can enqueue malicious jobs | Enable Redis AUTH; use TLS for Redis connections; restrict network access |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress feedback during document ingestion | User re-uploads thinking it failed; duplicate processing | Return job ID immediately; provide polling endpoint or webhook for status updates |
| Silent conversion failures | User thinks document was ingested; searches return nothing | Explicit failure notification with actionable error message (e.g., "PDF appears to be scanned; OCR extraction produced limited results") |
| No partial success reporting | One bad page fails entire document ingestion | Report per-page/per-section status; ingest what succeeds; flag what failed |
| Returning empty search results without explanation | User assumes system is broken | Distinguish "no results found" from "search error"; suggest query reformulations |
| Mixing search results across document types | User cannot filter by source type | Expose document type, source, and date as faceted filters in search results |
| No indication of retrieval confidence | User treats all results as equally reliable | Show similarity scores or confidence indicators; clearly mark low-confidence results |
| Ingestion status only visible via API | Non-technical users cannot monitor pipeline health | Build simple status dashboard showing queue depth, processing rate, error rate |

---

## "Looks Done But Isn't" Checklist

- [ ] **Chunking tested with real documents** -- not just clean markdown files. Test with scanned PDFs, complex tables, multi-column layouts, documents in multiple languages.
- [ ] **Cross-tenant isolation verified** -- ingest as Tenant A, search as Tenant B, assert zero results. Verify in MongoDB, Qdrant, Redis cache, and file storage.
- [ ] **Embedding model versioned and recorded** -- every vector has metadata recording which model/version produced it. Migration path exists for model upgrades.
- [ ] **Conversion timeout and fallback tested** -- submit a malformed PDF that causes Docling to hang. Verify timeout fires, worker recovers, user gets error message.
- [ ] **Memory behavior under load tested** -- run sustained ingestion (100+ documents) and monitor RSS over time. Verify no unbounded growth. Test with large files (50+ page PDFs).
- [ ] **Payload indexes created before data** -- verify Qdrant collection has indexes on tenant_id (and any other filter fields) before first upsert.
- [ ] **Search quality evaluated with real queries** -- not just "does it return something" but "does it return the RIGHT thing." Measure recall@K and precision.
- [ ] **Job failure and retry tested** -- kill a worker mid-processing. Verify job is retried, document state is consistent, no partial/corrupt data in vector store.
- [ ] **Cache invalidation works** -- update a document, verify search results reflect the update, not stale cached embeddings.
- [ ] **Large document handling tested** -- 100+ page PDF, 10MB+ DOCX. Verify it does not OOM the worker, timeout gracefully if too large, and produces reasonable chunks.
- [ ] **Empty/corrupt input handled** -- empty PDF, zero-byte file, password-protected document, non-UTF8 encoding. Verify graceful error, not crash.
- [ ] **Concurrent ingestion tested** -- multiple tenants uploading simultaneously. Verify no cross-contamination, no deadlocks, no race conditions in job queue.
- [ ] **Deletion works end-to-end** -- delete a document, verify chunks removed from Qdrant, metadata removed from MongoDB, cache invalidated, file removed from storage.
- [ ] **Re-indexing pipeline exists and is tested** -- can you re-embed all documents for a tenant without downtime? Without affecting other tenants?
- [ ] **Monitoring and alerting in place** -- alerts on: worker OOM, queue depth spike, Qdrant search latency, conversion error rate, Redis memory usage.

---

## Recovery Strategies

| Failure Scenario | Detection | Recovery Approach | Prevention |
|-----------------|-----------|-------------------|------------|
| Stuck conversion job (Docling hang) | Job exceeds timeout; worker heartbeat stops | Kill worker process; re-enqueue with retry counter; after max retries, mark as failed and notify user | Hard timeout on conversion; process isolation |
| Corrupt vectors in Qdrant (bad embedding) | Search quality degradation; anomalous similarity scores | Delete affected vectors by document ID; re-ingest from source document | Validate embedding dimensions and non-NaN values before upsert |
| Cross-tenant data leakage discovered | Audit log review; tenant reports seeing foreign documents | Immediate: disable affected queries. Remediate: identify scope of leak, purge leaked data, notify affected tenants, fix filter gap | Mandatory tenant filter injection; isolation tests in CI |
| Embedding model deprecated by provider | API errors on embedding calls; ingestion pipeline stops | Switch to new model; re-index all vectors (requires full re-embedding) | Use open-source models; maintain model version metadata; have re-indexing pipeline ready |
| Worker OOM during large document processing | Container restart; job marked as failed in queue | Reduce max_jobs concurrency; increase container memory limit; implement document size pre-check | Document size limits; jemalloc allocator; worker memory monitoring |
| Qdrant collection corruption | Search returns errors; collection health check fails | Restore from Qdrant snapshot; if no snapshot, re-index from MongoDB source metadata | Regular Qdrant snapshots; MongoDB as source of truth for document metadata |
| Redis data loss (cache + queue) | Jobs disappear; cache miss rate spikes | Queue: re-scan MongoDB for incomplete ingestion jobs, re-enqueue. Cache: self-heals on next access (cache-aside pattern) | Redis persistence (RDB+AOF); do not use Redis as sole state store for critical data |
| MongoDB connection exhaustion | "too many connections" errors; API 500s | Restart connection pool; reduce pool size; check for connection leaks in async code | Connection pooling with Motor; explicit pool size limits; connection leak detection |

---

## Pitfall-to-Phase Mapping

| Phase | Pitfalls to Watch For |
|-------|----------------------|
| **Architecture/Design** | Collection-per-tenant anti-pattern; no embedding versioning strategy; no tenant isolation design; synchronous processing architecture; no conversion fallback chain planned |
| **Implementation** | Missing tenant filters in queries; no payload indexes; no conversion timeouts; hardcoded embedding model; no batch processing for embeddings; cache keys without tenant prefix |
| **Testing** | Single-tenant test data only; clean documents only; no memory/load testing; no cross-tenant isolation tests; synthetic queries instead of real ones; no evaluation metrics |
| **Deployment** | Docker bind mounts on Windows/WSL; missing Qdrant health checks in startup; insufficient container memory limits; Redis without AUTH; Qdrant API without authentication |
| **Operations** | No monitoring for memory growth; no alerts on search latency; no re-indexing pipeline; no snapshot/backup strategy for Qdrant; no audit logging; stale evaluation datasets |

---

## Sources

### Chunking and Retrieval
- [Breaking Up Is Hard to Do: Chunking in RAG Applications (Stack Overflow Blog)](https://stackoverflow.blog/2024/12/27/breaking-up-is-hard-to-do-chunking-in-rag-applications/)
- [Chunking Strategies for RAG (Weaviate)](https://weaviate.io/blog/chunking-strategies-for-rag)
- [Why Your RAG System Fails and How Semantic Chunking Fixes It (Nimble Approach)](https://nimbleapproach.com/blog/why-your-rag-system-fails-the-critical-role-of-semantic-chunking/)
- [23 RAG Pitfalls and How to Fix Them](https://www.nb-data.com/p/23-rag-pitfalls-and-how-to-fix-them)
- [Seven Failure Points When Engineering a RAG System (arXiv)](https://arxiv.org/html/2401.05856v1)
- [Optimizing RAG with Hybrid Search and Reranking (Superlinked)](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking)

### Embedding Models
- [Different Embedding Models, Different Spaces: The Hidden Cost of Model Upgrades (Medium)](https://medium.com/data-science-collective/different-embedding-models-different-spaces-the-hidden-cost-of-model-upgrades-899db24ad233)
- [How to Fix Gemini/LangChain Embedding Dimension Mismatch (Medium)](https://medium.com/@henilsuhagiya0/how-to-fix-the-common-gemini-langchain-embedding-dimension-mismatch-768-vs-3072-6eb1c468729b)
- [Early Signs Your Vector Database Strategy Is Flawed (DevX)](https://www.devx.com/technology/early-signs-your-vector-database-strategy-is-flawed/)
- [RAG Trick: Embeddings are Spheres (Tim Kellogg)](https://timkellogg.me/blog/2024/07/10/spheres)

### Qdrant and Vector Search
- [Qdrant Multitenancy Guide](https://qdrant.tech/documentation/guides/multitenancy/)
- [Qdrant Payload Indexing](https://qdrant.tech/documentation/concepts/indexing/)
- [A Complete Guide to Filtering in Vector Search (Qdrant)](https://qdrant.tech/articles/vector-search-filtering/)
- [Vector Search in Production (Qdrant)](https://qdrant.tech/articles/vector-search-production/)
- [Vector Database Security and Qdrant (IronCore Labs)](https://ironcorelabs.com/vectordbs/qdrant-security/)
- [Qdrant 1.16 Tiered Multitenancy](https://qdrant.tech/blog/qdrant-1.16.x/)

### Multi-Tenancy and Security
- [OWASP Multi-Tenant Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)
- [Tenant Data Isolation: Patterns and Anti-Patterns (Propelius)](https://propelius.ai/blogs/tenant-data-isolation-patterns-and-anti-patterns)
- [Data Isolation in Multi-Tenant SaaS (Redis)](https://redis.io/blog/data-isolation-multi-tenant-saas/)
- [Tenant Isolation in Multi-Tenant Systems (WorkOS)](https://workos.com/blog/tenant-isolation-in-multi-tenant-systems)

### Document Conversion
- [Docling: Efficient Open-Source Toolkit for AI-driven Document Conversion (arXiv)](https://arxiv.org/html/2501.17887v1)
- [Docling Hangs on Some PDFs (GitHub Issue #2109)](https://github.com/docling-project/docling/issues/2109)
- [Docling Complex Table Layout Issues (GitHub Discussion #2241)](https://github.com/docling-project/docling/discussions/2241)
- [Docling vs. Graphlit: When Open-Source Falls Short](https://www.graphlit.com/vs/docling)
- [PDF to Markdown Conversion Tools: Beyond the Hype (Systenics AI)](https://systenics.ai/blog/2025-07-28-pdf-to-markdown-conversion-tools/)

### Pipeline Reliability and Memory
- [Fragmented Pages, Not Leaks: Fixing FastAPI's Memory Crisis (Medium)](https://medium.com/@shreehari9481/fragmented-pages-not-leaks-fixing-fastapis-memory-crisis-11da8f6a3065)
- [Chasing a Memory Leak in Our Async FastAPI Service (BetterUp)](https://build.betterup.com/chasing-a-memory-leak-in-our-async-fastapi-service-how-jemalloc-fixed-our-rss-creep/)
- [FastAPI Memory Usage OOM (GitHub Issue #1624)](https://github.com/fastapi/fastapi/issues/1624)
- [ARQ Retry on Timeout (GitHub Issue #401)](https://github.com/python-arq/arq/issues/401)
- [ARQ Job Aborts Failing (GitHub Issue #405)](https://github.com/samuelcolvin/arq/issues/405)
- [The Infrastructure Awakening: Why Your RAG Pilot Guarantees Production Failure](https://ragaboutit.com/the-infrastructure-awakening-why-your-rag-pilot-success-guarantees-production-failure/)

### Testing and Evaluation
- [Synthetic Data for RAG Evaluation (Red Hat)](https://developers.redhat.com/articles/2026/02/23/synthetic-data-rag-evaluation-why-your-rag-system-needs-better-testing)
- [Production-Ready RAG Pipeline Engineering Checklist (ActiveWizards)](https://activewizards.com/blog/the-production-ready-rag-pipeline-an-engineering-checklist)
- [RAG Evaluation: Complete Guide (Evidently AI)](https://www.evidentlyai.com/llm-guide/rag-evaluation)
- [Why Your RAG Pipeline Is Secretly Broken (Medium)](https://medium.com/@pragnesh.nprajapati/why-your-rag-pipeline-is-secretly-broken-and-how-to-fix-it-db56cacfbfdf)
