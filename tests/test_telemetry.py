"""Tests for docingest.services.telemetry — all offline (no network, no Mongo)."""

from __future__ import annotations

from types import SimpleNamespace

import httpx

from docingest.services import telemetry


def test_bucket_count_boundaries():
    assert telemetry.bucket_count(0) == "0"
    assert telemetry.bucket_count(-5) == "0"
    assert telemetry.bucket_count(9) == "1-9"
    assert telemetry.bucket_count(10) == "10-99"
    assert telemetry.bucket_count(999) == "100-999"
    assert telemetry.bucket_count(5000) == "1k-9k"
    assert telemetry.bucket_count(250_000) == "100k+"


def test_build_payload_shape_is_anonymous():
    payload = telemetry.build_payload("abc123", doc_count=42, graph_enabled=True)
    assert payload["event"] == "heartbeat"
    assert payload["instance_id"] == "abc123"
    assert payload["documents"] == "10-99"  # bucketed, not exact
    assert payload["graph_rag_enabled"] is True
    assert set(payload) == {
        "event", "instance_id", "version", "os", "python", "documents", "graph_rag_enabled"
    }
    # No exact document count or any obviously identifying field leaks through.
    assert 42 not in payload.values()


async def test_send_heartbeat_posts_payload():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["body"] = req.content
        return httpx.Response(200)

    ok = await telemetry.send_heartbeat(
        "https://example.test/hb", {"event": "heartbeat"},
        transport=httpx.MockTransport(handler),
    )
    assert ok is True
    assert seen["url"] == "https://example.test/hb"
    assert b"heartbeat" in seen["body"]


async def test_send_heartbeat_fails_silently_on_error_status():
    ok = await telemetry.send_heartbeat(
        "https://example.test/hb", {},
        transport=httpx.MockTransport(lambda req: httpx.Response(500)),
    )
    assert ok is False


async def test_send_heartbeat_fails_silently_on_exception():
    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    ok = await telemetry.send_heartbeat(
        "https://example.test/hb", {}, transport=httpx.MockTransport(boom)
    )
    assert ok is False


async def test_collect_and_send_noop_when_disabled(monkeypatch):
    called = False

    async def _should_not_run(*a, **k):
        nonlocal called
        called = True
        return "x"

    monkeypatch.setattr(telemetry, "get_or_create_instance_id", _should_not_run)
    settings = SimpleNamespace(
        telemetry_enabled=False, telemetry_endpoint="https://e", graph_rag_enabled=False
    )
    assert await telemetry.collect_and_send(db=None, settings=settings) is False
    assert called is False


async def test_collect_and_send_orchestrates_when_enabled(monkeypatch):
    sent = {}

    async def fake_id(db):
        return "inst-1"

    async def fake_count(db):
        return 5

    async def fake_send(endpoint, payload, *, transport=None):
        sent["endpoint"] = endpoint
        sent["payload"] = payload
        return True

    monkeypatch.setattr(telemetry, "get_or_create_instance_id", fake_id)
    monkeypatch.setattr(telemetry, "_count_documents", fake_count)
    monkeypatch.setattr(telemetry, "send_heartbeat", fake_send)

    settings = SimpleNamespace(
        telemetry_enabled=True,
        telemetry_endpoint="https://collector.test/hb",
        graph_rag_enabled=True,
    )
    ok = await telemetry.collect_and_send(db=object(), settings=settings)

    assert ok is True
    assert sent["endpoint"] == "https://collector.test/hb"
    assert sent["payload"]["instance_id"] == "inst-1"
    assert sent["payload"]["documents"] == "1-9"
    assert sent["payload"]["graph_rag_enabled"] is True
