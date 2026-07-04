"""Command-line interface for DocIngest (``docingest``).

A thin client over the DocIngest REST API for ingesting documents, searching,
and inspecting status. Configure with ``--api-url`` / ``--api-key`` or the
``DOCINGEST_API_URL`` / ``DOCINGEST_API_KEY`` environment variables.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from docingest.client import DocIngestClient, DocIngestError

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".html", ".htm", ".txt", ".md"}


def _emit(args: argparse.Namespace, obj: object) -> None:
    """Print raw JSON when --json is set; callers handle human output otherwise."""
    if getattr(args, "json", False):
        print(json.dumps(obj, indent=2))


def cmd_ingest(args: argparse.Namespace, client: DocIngestClient) -> int:
    target = args.target
    if target.startswith(("http://", "https://")):
        items = [("url", target)]
    else:
        path = Path(target)
        if path.is_dir():
            files = sorted(f for f in path.rglob("*") if f.suffix.lower() in SUPPORTED_SUFFIXES)
            if not files:
                print(f"no supported documents under {path}", file=sys.stderr)
                return 1
            items = [("file", str(f)) for f in files]
        elif path.is_file():
            items = [("file", target)]
        else:
            print(f"not a URL, file, or directory: {target}", file=sys.stderr)
            return 1

    results = []
    for kind, src in items:
        if kind == "url":
            res = client.ingest_url(src, force=args.force)
        else:
            res = client.ingest_file(src, force=args.force)
        doc_id = res.get("id")
        status = res.get("status")
        if args.wait and doc_id and status != "duplicate":
            res = client.wait_for(doc_id)
            status = res.get("status")
        results.append(res)
        print(f"{doc_id}  {status}  {Path(src).name if kind == 'file' else src}")
    _emit(args, results if len(results) > 1 else results[0])
    return 0


def cmd_search(args: argparse.Namespace, client: DocIngestClient) -> int:
    res = client.search(args.query, limit=args.limit, rerank=not args.no_rerank)
    for i, r in enumerate(res.get("results", []), 1):
        chain = " > ".join(r.get("heading_chain", [])) or r.get("source_ref", "")
        snippet = " ".join(r.get("chunk_text", "").split())[:160]
        print(f"{i:>2}. [{r.get('score', 0):.4f}] {chain}\n    {snippet}")
    print(f"\n{len(res.get('results', []))} results in {res.get('search_time_ms', 0)}ms")
    _emit(args, res)
    return 0


def cmd_status(args: argparse.Namespace, client: DocIngestClient) -> int:
    doc = client.get_document(args.doc_id)
    print(f"id:      {doc.get('id')}")
    print(f"status:  {doc.get('status')}")
    print(f"source:  {doc.get('source_ref')}")
    print(f"chunks:  {doc.get('chunk_count')}")
    if doc.get("error"):
        print(f"error:   {doc['error']}")
    _emit(args, doc)
    return 0


def cmd_list(args: argparse.Namespace, client: DocIngestClient) -> int:
    res = client.list_documents(status=args.status, per_page=args.limit)
    for d in res.get("documents", []):
        cc = d.get("chunk_count")
        print(f"{d.get('id')}  {d.get('status'):<11}  {cc:>4} chunks  {d.get('source_ref')}")
    print(f"\n{res.get('total', 0)} total")
    _emit(args, res)
    return 0


def cmd_delete(args: argparse.Namespace, client: DocIngestClient) -> int:
    client.delete_document(args.doc_id)
    print(f"deleted {args.doc_id}")
    return 0


def cmd_health(args: argparse.Namespace, client: DocIngestClient) -> int:
    res = client.health()
    print(f"status: {res.get('status')}")
    for name, state in res.get("checks", {}).items():
        print(f"  {name:<8} {state}")
    _emit(args, res)
    return 0 if res.get("status") == "healthy" else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="docingest", description="DocIngest command-line client.")
    p.add_argument("--api-url", default=None, help="API base URL (env: DOCINGEST_API_URL)")
    p.add_argument("--api-key", default=None, help="API key (env: DOCINGEST_API_KEY)")
    p.add_argument("--json", action="store_true", help="Also print the raw JSON response")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("ingest", help="Ingest a file, directory, or URL")
    pi.add_argument("target", help="File path, directory, or http(s) URL")
    pi.add_argument("--wait", action="store_true", help="Poll until processing completes")
    pi.add_argument("--force", action="store_true", help="Ingest even if a duplicate exists")
    pi.set_defaults(func=cmd_ingest)

    ps = sub.add_parser("search", help="Semantic search")
    ps.add_argument("query")
    ps.add_argument("--limit", type=int, default=10)
    ps.add_argument("--no-rerank", action="store_true", help="Disable cross-encoder reranking")
    ps.set_defaults(func=cmd_search)

    pt = sub.add_parser("status", help="Show a document's status")
    pt.add_argument("doc_id")
    pt.set_defaults(func=cmd_status)

    pl = sub.add_parser("list", help="List documents")
    pl.add_argument("--status", default=None, help="Filter by status")
    pl.add_argument("--limit", type=int, default=50)
    pl.set_defaults(func=cmd_list)

    pd = sub.add_parser("delete", help="Delete a document")
    pd.add_argument("doc_id")
    pd.set_defaults(func=cmd_delete)

    ph = sub.add_parser("health", help="Check service health")
    ph.set_defaults(func=cmd_health)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with DocIngestClient(base_url=args.api_url, api_key=args.api_key) as client:
            return args.func(args, client)
    except DocIngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
