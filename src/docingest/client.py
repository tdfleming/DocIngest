"""Synchronous client for the DocIngest REST API.

Shared by the CLI (``docingest``) and the MCP server (``docingest-mcp``) so that
request/response logic lives in exactly one place. Configuration is read from
``DOCINGEST_API_URL`` and ``DOCINGEST_API_KEY`` unless passed explicitly.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_URL = "http://localhost:8000"
TERMINAL_STATUSES = frozenset({"complete", "failed"})


class DocIngestError(RuntimeError):
    """Raised when the DocIngest API is unreachable or returns an error status."""


class DocIngestClient:
    """Thin synchronous wrapper over the DocIngest ``/v1`` API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("DOCINGEST_API_URL", DEFAULT_URL)).rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("DOCINGEST_API_KEY", "")
        headers = {"X-API-Key": self.api_key} if self.api_key else {}
        self._http = httpx.Client(
            base_url=self.base_url, headers=headers, timeout=timeout, transport=transport
        )

    def __enter__(self) -> DocIngestClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise DocIngestError(f"request to {path} failed: {exc}") from exc
        if resp.status_code >= 400:
            raise DocIngestError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}")
        if resp.content and resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return None

    # --- documents -------------------------------------------------------
    def ingest_file(self, path: str | Path, *, force: bool = False) -> dict:
        p = Path(path)
        if not p.is_file():
            raise DocIngestError(f"not a file: {p}")
        with p.open("rb") as fh:
            return self._request(
                "POST", "/v1/documents",
                params={"force": str(force).lower()},
                files={"file": (p.name, fh)},
            )

    def ingest_url(self, url: str, *, force: bool = False) -> dict:
        return self._request(
            "POST", "/v1/documents/url", params={"force": str(force).lower()}, json={"url": url}
        )

    def get_document(self, doc_id: str) -> dict:
        return self._request("GET", f"/v1/documents/{doc_id}")

    def list_documents(
        self, *, status: str | None = None, page: int = 1, per_page: int = 50
    ) -> dict:
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if status:
            params["status"] = status
        return self._request("GET", "/v1/documents", params=params)

    def delete_document(self, doc_id: str) -> None:
        self._request("DELETE", f"/v1/documents/{doc_id}")

    def wait_for(self, doc_id: str, *, interval: float = 1.0, timeout: float = 600.0) -> dict:
        """Poll a document until it reaches a terminal status or the timeout elapses."""
        deadline = time.monotonic() + timeout
        while True:
            doc = self.get_document(doc_id)
            if doc.get("status") in TERMINAL_STATUSES or time.monotonic() > deadline:
                return doc
            time.sleep(interval)

    # --- search ----------------------------------------------------------
    def search(self, query: str, *, limit: int = 10, rerank: bool = True) -> dict:
        return self._request(
            "POST", "/v1/search", json={"query": query, "limit": limit, "rerank": rerank}
        )

    def graph_search(self, query: str, *, limit: int = 5) -> dict:
        return self._request("POST", "/v1/graph/search", json={"query": query, "limit": limit})

    # --- health ----------------------------------------------------------
    def health(self) -> dict:
        """Return the health payload even when degraded (the API returns 503 then)."""
        try:
            resp = self._http.get("/v1/health")
        except httpx.HTTPError as exc:
            raise DocIngestError(f"health check failed: {exc}") from exc
        return resp.json()
