"""MCP server exposing DocIngest to AI agents (Claude Code, Cursor, Claude Desktop).

Wraps the DocIngest REST API as MCP tools so an agent can ingest documents and
search them directly. Configure via ``DOCINGEST_API_URL`` and ``DOCINGEST_API_KEY``.

Run with the ``docingest-mcp`` entry point (stdio transport). Requires the ``mcp``
extra: ``pip install "docingest[mcp]"``.

The ``mcp`` SDK is imported lazily inside ``build_server`` so this module can be
imported (and linted) without the optional dependency installed.
"""

from __future__ import annotations

import asyncio
from typing import Any

from docingest.client import DocIngestClient


def build_server(client: DocIngestClient | None = None) -> Any:
    """Construct the FastMCP server with DocIngest tools registered."""
    from mcp.server.fastmcp import FastMCP

    client = client or DocIngestClient()
    mcp = FastMCP("docingest")

    @mcp.tool()
    async def ingest_document(source: str, wait: bool = False) -> dict:
        """Ingest a document into DocIngest.

        `source` is an http(s) URL or a local file path (PDF/DOCX/HTML/TXT/MD).
        Set `wait=true` to block until conversion, chunking, and embedding finish.
        """
        def _do() -> dict:
            if source.startswith(("http://", "https://")):
                res = client.ingest_url(source)
            else:
                res = client.ingest_file(source)
            doc_id = res.get("id")
            if wait and doc_id:
                return client.wait_for(doc_id)
            return res

        return await asyncio.to_thread(_do)

    @mcp.tool()
    async def search(query: str, limit: int = 10) -> dict:
        """Semantic search over ingested documents (vector retrieval + reranking)."""
        return await asyncio.to_thread(lambda: client.search(query, limit=limit))

    @mcp.tool()
    async def get_document_status(document_id: str) -> dict:
        """Get processing status and metadata for a previously ingested document."""
        return await asyncio.to_thread(lambda: client.get_document(document_id))

    @mcp.tool()
    async def list_documents(status: str | None = None, limit: int = 20) -> dict:
        """List ingested documents, optionally filtered by status."""
        return await asyncio.to_thread(lambda: client.list_documents(status=status, per_page=limit))

    @mcp.tool()
    async def graph_search(query: str, limit: int = 5) -> dict:
        """Search the knowledge-graph community summaries (requires GRAPH_RAG_ENABLED)."""
        return await asyncio.to_thread(lambda: client.graph_search(query, limit=limit))

    return mcp


def main() -> None:
    """Entry point: run the MCP server over stdio."""
    build_server().run()


if __name__ == "__main__":
    main()
