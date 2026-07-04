"""Tests for docingest.client.DocIngestClient using an in-memory httpx transport."""

from __future__ import annotations

import json

import httpx
import pytest

from docingest.client import DocIngestClient, DocIngestError


def make_client(handler, **kwargs) -> DocIngestClient:
    return DocIngestClient(
        base_url="http://test", api_key="k", transport=httpx.MockTransport(handler), **kwargs
    )


def test_search_posts_expected_body_and_header():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["method"] = req.method
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        seen["api_key"] = req.headers.get("x-api-key")
        return httpx.Response(200, json={"results": [{"score": 0.9}], "search_time_ms": 5})

    with make_client(handler) as c:
        res = c.search("hello", limit=3, rerank=False)

    assert seen["method"] == "POST"
    assert seen["path"] == "/v1/search"
    assert seen["body"] == {"query": "hello", "limit": 3, "rerank": False}
    assert seen["api_key"] == "k"
    assert res["results"][0]["score"] == 0.9


def test_ingest_url_sends_body_and_force_param():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(202, json={"id": "abc", "status": "pending"})

    with make_client(handler) as c:
        res = c.ingest_url("http://x/y.pdf", force=True)

    assert "/v1/documents/url" in seen["url"]
    assert "force=true" in seen["url"]
    assert seen["body"] == {"url": "http://x/y.pdf"}
    assert res["id"] == "abc"


def test_list_documents_query_params():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"documents": [], "total": 0, "page": 2, "per_page": 10})

    with make_client(handler) as c:
        c.list_documents(status="complete", page=2, per_page=10)

    assert "page=2" in seen["url"]
    assert "per_page=10" in seen["url"]
    assert "status=complete" in seen["url"]


def test_ingest_file_uploads_multipart(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("hello")
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["ctype"] = req.headers.get("content-type", "")
        return httpx.Response(202, json={"id": "1", "status": "pending"})

    with make_client(handler) as c:
        res = c.ingest_file(f)

    assert seen["path"] == "/v1/documents"
    assert seen["ctype"].startswith("multipart/form-data")
    assert res["id"] == "1"


def test_ingest_missing_file_raises():
    with make_client(lambda req: httpx.Response(200)) as c, pytest.raises(DocIngestError):
        c.ingest_file("/nope/missing.pdf")


def test_error_status_raises():
    with (
        make_client(lambda req: httpx.Response(404, json={"error": "nope"})) as c,
        pytest.raises(DocIngestError),
    ):
        c.get_document("x")


def test_delete_no_content_returns_none():
    with make_client(lambda req: httpx.Response(204)) as c:
        assert c.delete_document("1") is None


def test_health_returns_body_even_when_degraded():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"status": "degraded", "checks": {"mongodb": "error"}})

    with make_client(handler) as c:
        res = c.health()

    assert res["status"] == "degraded"


def test_wait_for_polls_until_terminal():
    seq = iter(["chunking", "complete"])

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "1", "status": next(seq)})

    with make_client(handler) as c:
        doc = c.wait_for("1", interval=0)

    assert doc["status"] == "complete"
