#!/usr/bin/env python3
"""DocIngest benchmark harness.

Measures the *real* ingestion and search performance of a running DocIngest
instance against a corpus of your own documents. It produces reproducible
numbers on your hardware — it does NOT ship canned results.

What it measures:
  - Ingestion: end-to-end wall time per document (upload -> COMPLETE), overall
    documents/sec and MB/sec throughput, chunks produced.
  - Search: client-side round-trip latency and server-reported search_time_ms,
    with p50/p95 across repeated queries.

It only benchmarks DocIngest itself (a single-system benchmark). Head-to-head
comparisons with hosted services require running those services yourself; see
docs/benchmarks.md for the capability/pricing comparison and methodology.

Usage:
  python scripts/benchmark.py \
      --api-url http://localhost:8000 \
      --api-key "$DOCINGEST_API_KEY" \
      --corpus ./sample-docs \
      --queries ./queries.txt \
      --repeat 20 \
      --output bench-report.json

Requires: httpx (a DocIngest dependency; `pip install httpx` if running standalone).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import httpx

TERMINAL_OK = "complete"
TERMINAL_FAIL = "failed"
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".html", ".htm", ".txt", ".md"}
DEFAULT_QUERIES = [
    "summary of the main topic",
    "key findings and conclusions",
    "definitions and terminology",
]


def _pct(values: list[float], p: float) -> float:
    """Return the p-th percentile (0-100) of values, or 0.0 if empty."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def ingest_document(
    client: httpx.Client, path: Path, poll_interval: float, timeout: float
) -> dict:
    """Upload one document and poll to completion. Returns a per-doc result dict."""
    started = time.monotonic()
    with path.open("rb") as fh:
        resp = client.post(
            "/v1/documents", params={"force": "true"}, files={"file": (path.name, fh)}
        )
    resp.raise_for_status()
    doc_id = resp.json()["id"]

    status = "pending"
    error = None
    chunk_count = 0
    while time.monotonic() - started < timeout:
        time.sleep(poll_interval)
        r = client.get(f"/v1/documents/{doc_id}")
        r.raise_for_status()
        body = r.json()
        status = body.get("status", "unknown")
        chunk_count = body.get("chunk_count", 0)
        if status == TERMINAL_OK:
            break
        if status == TERMINAL_FAIL:
            error = body.get("error")
            break
    elapsed = time.monotonic() - started

    return {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "status": status,
        "error": error,
        "chunk_count": chunk_count,
        "ingest_seconds": round(elapsed, 3),
    }


def run_searches(client: httpx.Client, queries: list[str], repeat: int) -> dict:
    """Run each query `repeat` times, measuring client and server latency."""
    client_ms: list[float] = []
    server_ms: list[float] = []
    result_counts: list[int] = []
    for _ in range(repeat):
        for q in queries:
            t0 = time.monotonic()
            r = client.post("/v1/search", json={"query": q, "limit": 10, "rerank": True})
            r.raise_for_status()
            client_ms.append((time.monotonic() - t0) * 1000)
            body = r.json()
            server_ms.append(float(body.get("search_time_ms", 0)))
            result_counts.append(len(body.get("results", [])))
    return {
        "queries": len(queries),
        "runs": len(client_ms),
        "avg_results": round(statistics.mean(result_counts), 1) if result_counts else 0,
        "client_ms_p50": round(_pct(client_ms, 50), 1),
        "client_ms_p95": round(_pct(client_ms, 95), 1),
        "server_ms_p50": round(_pct(server_ms, 50), 1),
        "server_ms_p95": round(_pct(server_ms, 95), 1),
    }


def summarize(docs: list[dict]) -> dict:
    ok = [d for d in docs if d["status"] == TERMINAL_OK]
    total_seconds = sum(d["ingest_seconds"] for d in docs)
    total_mb = sum(d["size_bytes"] for d in docs) / (1024 * 1024)
    total_chunks = sum(d["chunk_count"] for d in ok)
    return {
        "documents": len(docs),
        "succeeded": len(ok),
        "failed": len(docs) - len(ok),
        "total_mb": round(total_mb, 2),
        "total_chunks": total_chunks,
        "avg_chunks_per_doc": round(total_chunks / len(ok), 1) if ok else 0,
        "wall_seconds": round(total_seconds, 1),
        "docs_per_sec": round(len(ok) / total_seconds, 3) if total_seconds else 0,
        "mb_per_sec": round(total_mb / total_seconds, 3) if total_seconds else 0,
        "ingest_p50_s": round(_pct([d["ingest_seconds"] for d in ok], 50), 2),
        "ingest_p95_s": round(_pct([d["ingest_seconds"] for d in ok], 95), 2),
    }


def print_report(summary: dict, search: dict) -> None:
    print("\n=== DocIngest benchmark ===")
    print("\nIngestion")
    print(f"  documents:          {summary['succeeded']}/{summary['documents']} ok")
    print(f"  data:               {summary['total_mb']} MB, {summary['total_chunks']} chunks "
          f"({summary['avg_chunks_per_doc']} chunks/doc)")
    print(f"  throughput:         {summary['docs_per_sec']} docs/s, {summary['mb_per_sec']} MB/s")
    print(f"  per-doc latency:    p50 {summary['ingest_p50_s']}s / p95 {summary['ingest_p95_s']}s")
    if search:
        c = search
        print("\nSearch")
        print(f"  runs:               {c['runs']} ({c['queries']} queries)")
        print(f"  client latency:     p50 {c['client_ms_p50']}ms / p95 {c['client_ms_p95']}ms")
        print(f"  server latency:     p50 {c['server_ms_p50']}ms / p95 {c['server_ms_p95']}ms")
        print(f"  avg results/query:  {c['avg_results']}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark a running DocIngest instance.")
    ap.add_argument("--api-url", default=os.environ.get("DOCINGEST_API_URL", "http://localhost:8000"))
    ap.add_argument("--api-key", default=os.environ.get("DOCINGEST_API_KEY", ""))
    ap.add_argument("--corpus", type=Path, required=True, help="Directory of documents to ingest")
    ap.add_argument("--queries", type=Path, help="File with one search query per line")
    ap.add_argument("--repeat", type=int, default=20, help="Search repetitions per query")
    ap.add_argument("--poll-interval", type=float, default=0.5)
    ap.add_argument("--timeout", type=float, default=600, help="Per-document ingest timeout (s)")
    ap.add_argument("--output", type=Path, help="Write full JSON report here")
    args = ap.parse_args()

    if not args.api_key:
        print("error: provide --api-key or set DOCINGEST_API_KEY", file=sys.stderr)
        return 2
    files = sorted(p for p in args.corpus.rglob("*") if p.suffix.lower() in SUPPORTED_SUFFIXES)
    if not files:
        print(f"error: no supported documents found under {args.corpus}", file=sys.stderr)
        return 2

    queries = DEFAULT_QUERIES
    if args.queries and args.queries.exists():
        raw = args.queries.read_text(encoding="utf-8").splitlines()
        queries = [ln.strip() for ln in raw if ln.strip()]

    client = httpx.Client(base_url=args.api_url, headers={"X-API-Key": args.api_key}, timeout=60.0)

    print(f"Ingesting {len(files)} document(s) from {args.corpus} ...")
    docs = []
    for i, path in enumerate(files, 1):
        result = ingest_document(client, path, args.poll_interval, args.timeout)
        flag = "ok" if result["status"] == TERMINAL_OK else result["status"].upper()
        print(f"  [{i}/{len(files)}] {path.name}: {flag} "
              f"({result['ingest_seconds']}s, {result['chunk_count']} chunks)")
        docs.append(result)

    summary = summarize(docs)
    print(f"\nRunning search benchmark ({len(queries)} queries x {args.repeat}) ...")
    search = run_searches(client, queries, args.repeat)

    print_report(summary, search)

    if args.output:
        report = {
            "api_url": args.api_url,
            "corpus": str(args.corpus),
            "ingestion": summary,
            "search": search,
            "documents": docs,
        }
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Full report written to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
