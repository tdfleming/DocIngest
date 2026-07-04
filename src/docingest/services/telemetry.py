"""Opt-in, anonymous telemetry.

**Disabled by default.** Nothing is ever sent unless the operator sets
``TELEMETRY_ENABLED=true``. When enabled, DocIngest sends a periodic heartbeat so
the maintainers can gauge how many instances are running and on what versions.

What a heartbeat contains — and nothing else:
  - a random, locally-generated instance id (no relation to any tenant/user/host)
  - the DocIngest version, OS name, and Python minor version
  - a coarse **bucket** of total document count (e.g. "10-99"), never an exact number
  - whether Graph RAG is enabled (boolean)

It never sends document content, tenant data, API keys, file names, IPs, or any
personal data. Sending is best-effort and fail-silent — it can never affect the app.
"""

from __future__ import annotations

import platform
import sys
import uuid
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

INSTANCE_DOC_ID = "telemetry-instance"


def get_version() -> str:
    try:
        return _pkg_version("docingest")
    except PackageNotFoundError:
        return "unknown"


def bucket_count(n: int) -> str:
    """Map an exact count to a coarse, non-identifying magnitude bucket."""
    if n <= 0:
        return "0"
    if n < 10:
        return "1-9"
    if n < 100:
        return "10-99"
    if n < 1_000:
        return "100-999"
    if n < 10_000:
        return "1k-9k"
    if n < 100_000:
        return "10k-99k"
    return "100k+"


def build_payload(instance_id: str, doc_count: int, graph_enabled: bool) -> dict[str, Any]:
    """Assemble the anonymous heartbeat payload (pure function)."""
    return {
        "event": "heartbeat",
        "instance_id": instance_id,
        "version": get_version(),
        "os": platform.system(),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "documents": bucket_count(doc_count),
        "graph_rag_enabled": bool(graph_enabled),
    }


async def get_or_create_instance_id(db: Any) -> str:
    """Fetch (or create) the persistent anonymous instance id from MongoDB."""
    coll = db.telemetry
    existing = await coll.find_one({"_id": INSTANCE_DOC_ID})
    if existing and existing.get("instance_id"):
        return existing["instance_id"]
    instance_id = uuid.uuid4().hex
    await coll.update_one(
        {"_id": INSTANCE_DOC_ID},
        {"$setOnInsert": {"instance_id": instance_id}},
        upsert=True,
    )
    # Re-read in case of a concurrent insert winning the race.
    doc = await coll.find_one({"_id": INSTANCE_DOC_ID})
    return doc["instance_id"] if doc else instance_id


async def _count_documents(db: Any) -> int:
    try:
        return await db.documents.count_documents({})
    except Exception:  # noqa: BLE001 - telemetry must never raise
        return 0


async def send_heartbeat(
    endpoint: str,
    payload: dict[str, Any],
    *,
    timeout: float = 5.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    """POST the payload; return True on success. Never raises."""
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            resp = await client.post(endpoint, json=payload)
        return resp.status_code < 400
    except Exception:  # noqa: BLE001 - best-effort, fail silent
        return False


async def collect_and_send(db: Any, settings: Any, *, transport=None) -> bool:
    """Gather an anonymous heartbeat and send it, if telemetry is enabled."""
    if not settings.telemetry_enabled or not settings.telemetry_endpoint:
        return False
    instance_id = await get_or_create_instance_id(db)
    doc_count = await _count_documents(db)
    payload = build_payload(instance_id, doc_count, settings.graph_rag_enabled)
    return await send_heartbeat(settings.telemetry_endpoint, payload, transport=transport)


async def telemetry_loop(db: Any, settings: Any) -> None:
    """Send a heartbeat on startup, then every ``telemetry_interval_hours``."""
    import asyncio

    interval = max(1, settings.telemetry_interval_hours) * 3600
    while True:
        try:
            await collect_and_send(db, settings)
        except Exception:  # noqa: BLE001 - never let telemetry crash the loop
            log.debug("telemetry heartbeat failed", exc_info=True)
        await asyncio.sleep(interval)
