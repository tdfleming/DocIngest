# Benchmarks & Comparison

!!! note "On honesty"
    We do **not** publish canned performance numbers or head-to-head charts against
    hosted competitors — we can't run their systems fairly, and ingestion speed is
    hardware/corpus-dependent. Instead we ship a reproducible harness you run yourself.

## Capability & pricing comparison

| | **DocIngest** | Unstructured | Ragie | LlamaCloud | RAGFlow |
|---|:---:|:---:|:---:|:---:|:---:|
| License | Apache-2.0 | partly OSS | closed | closed | Apache-2.0 |
| Self-host | ✅ | ✅ | ❌ | ❌ | ✅ |
| Parse → chunk → embed → **serve search** | ✅ | parse only | ✅ | parse-centric | ✅ |
| Built-in **multi-tenant isolation** | ✅ | ❌ | ❌ | ❌ | limited |
| **Knowledge graph** | ✅ | ❌ | ❌ | limited | ✅ |
| Local embeddings (no per-token cost) | ✅ | — | ❌ | ❌ | configurable |
| Managed cloud | 🔜 | ✅ | ✅ | ✅ | ✅ |
| Headline price | **self-host: free** | ~$0.01 / page | $100 / 10k pages | ~$1 / 1k credits | free (OSS) |

Pricing is from public vendor materials (mid-2026) and is directional — verify current pricing.

## Cost model

DocIngest runs conversion, embedding, and reranking **locally** — no per-page or per-token inference fee. Two consequences:

- **Re-indexing is free** — teams re-index 1–3× in the first six months as strategies change; here that's just CPU time.
- **Cost is flat and predictable** — a fixed cluster ingests as much as its throughput allows, independent of volume tiers.

## Reproducible performance harness

Measure your own instance with [`scripts/benchmark.py`](https://github.com/tdfleming/DocIngest/blob/master/scripts/benchmark.py):

```bash
export DOCINGEST_API_KEY="<your key>"
python scripts/benchmark.py \
  --api-url http://localhost:8000 \
  --corpus ./sample-docs \
  --queries ./queries.txt \
  --repeat 20 \
  --output bench-report.json
```

It reports ingestion throughput (docs/s, MB/s), per-document latency (p50/p95), chunk counts, and search latency (client + server, p50/p95). Always report your hardware alongside the numbers.

Full methodology and a results template: [docs/benchmarks.md](https://github.com/tdfleming/DocIngest/blob/master/docs/benchmarks.md).
