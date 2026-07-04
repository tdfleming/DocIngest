# Benchmarks & Comparison

This document has two parts:

1. **Capability & pricing comparison** — how DocIngest compares to popular ingestion / RAG platforms, from public docs. Sourced; no cherry-picking.
2. **Performance methodology** — a reproducible harness ([`scripts/benchmark.py`](../scripts/benchmark.py)) you run on your own hardware and corpus.

> **On honesty:** we do **not** publish canned performance numbers or head-to-head
> latency charts against hosted competitors. We can't run their systems fairly, and
> ingestion speed depends heavily on hardware, document mix, and settings. Instead we
> ship the harness and a results template — run it and report what *you* measure.

---

## 1. Capability & pricing comparison

| | **DocIngest** | Unstructured | Ragie | LlamaCloud | RAGFlow |
|---|:---:|:---:|:---:|:---:|:---:|
| License | Apache-2.0 | partly OSS | closed | closed | Apache-2.0 |
| Self-host | ✅ | ✅ | ❌ | ❌ | ✅ |
| Parse → chunk → embed → **serve search** | ✅ | parse only | ✅ | parse-centric | ✅ |
| Built-in **multi-tenant isolation** | ✅ | ❌ | ❌ | ❌ | limited |
| **Knowledge graph** (entities + communities) | ✅ | ❌ | ❌ | limited | ✅ |
| Local embeddings (no per-token cost) | ✅ | — | ❌ | ❌ | configurable |
| Reranking | ✅ local cross-encoder | ❌ | ✅ | ✅ | ✅ |
| Managed cloud | 🔜 | ✅ | ✅ | ✅ | ✅ |
| Headline price | **self-host: free** | ~$0.01 / page | $100 / 10k pages → $500 / 60k | ~$1 / 1,000 credits (3–45 credits/page); 10k free credits/mo | free (OSS) |

Pricing figures are from each vendor's public materials as of mid-2026 (see [Sources](#sources)); confirm current pricing before relying on it.

### Cost model — where DocIngest is structurally different

DocIngest runs **conversion, embedding, and reranking locally** (Docling, FastEmbed, an ONNX cross-encoder). There is **no per-page or per-token inference fee** — you pay only for the compute you already run. Two consequences:

- **Re-indexing is free.** Teams typically re-index 1–3× in the first six months as chunking/embedding strategies change. On per-page/per-credit services you pay for every re-index; here it's just CPU time.
- **Cost is predictable and flat.** A fixed cluster ingests as many documents as it has throughput for, regardless of volume-based pricing tiers.

The trade-off is that you provide the compute and operate the stack (or use the managed cloud when available).

---

## 2. Performance methodology

The harness measures DocIngest's **own** pipeline end-to-end against a corpus you provide. It is a single-system benchmark, not a head-to-head — but it's fully reproducible.

### What it measures

**Ingestion** (per document, upload → `COMPLETE`)
- wall-clock latency (p50 / p95), documents/sec, MB/sec
- chunks produced (total, avg per document)

**Search**
- client round-trip latency and server-reported `search_time_ms` (p50 / p95) over repeated queries, with reranking enabled

### Run it

```bash
# 1. A running DocIngest instance + a tenant API key
export DOCINGEST_API_KEY="<your key>"

# 2. A corpus directory (PDF/DOCX/HTML/TXT/MD) and optional queries file
python scripts/benchmark.py \
  --api-url http://localhost:8000 \
  --corpus ./sample-docs \
  --queries ./queries.txt \
  --repeat 20 \
  --output bench-report.json
```

The script prints a summary and writes full per-document JSON to `--output`. Fields: `ingestion.{docs_per_sec, mb_per_sec, ingest_p50_s, ingest_p95_s, total_chunks}` and `search.{client_ms_p50/p95, server_ms_p50/p95}`.

### Report your results

Fill this in from `bench-report.json` and include your hardware — numbers are meaningless without it:

| Field | Value |
|---|---|
| Hardware (CPU / RAM / GPU) | _e.g. 8-core / 16 GB / none_ |
| Worker replicas (converter / chunker) | _2 / 2_ |
| Corpus (docs, total MB, type) | _… PDFs_ |
| Ingest throughput (docs/s · MB/s) | _…_ |
| Ingest latency p50 / p95 (s) | _…_ |
| Chunks (total · avg/doc) | _…_ |
| Search latency p50 / p95 — server (ms) | _…_ |
| Search latency p50 / p95 — client (ms) | _…_ |
| Embedding / reranking model | `bge-small-en-v1.5` / `ms-marco-MiniLM-L-6-v2` |

> Docling's first run downloads ~1.5 GB of layout models; exclude that cold-start from steady-state numbers, or run a warm-up document first. GPU on converter workers typically yields a 5–10× speedup on large or scanned PDFs.

---

## Sources

- Unstructured — pricing overview (per-page): https://unstructured.io
- Ragie — pricing tiers: https://www.ragie.ai
- LlamaCloud / LlamaParse — credit-based pricing: https://www.llamaindex.ai
- RAGFlow — open-source engine: https://github.com/infiniflow/ragflow
- Comparison context: https://atlan.com/know/enterprise-rag-platforms-comparison/ , https://www.meilisearch.com/blog/rag-as-a-service

Vendor pricing changes frequently — treat the figures above as directional and verify against current pricing pages.
