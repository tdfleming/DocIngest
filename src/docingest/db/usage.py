"""MongoDB storage for usage metering.

Usage events are the basis for quota enforcement and billing. Recording is
best-effort and never raises into the request path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase

from docingest.models.usage import UsageEventType

log = structlog.get_logger()


async def ensure_usage_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.usage_events.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.usage_events.create_index(
        [("tenant_id", 1), ("event_type", 1), ("created_at", -1)]
    )


def month_start(now: datetime) -> datetime:
    """First instant of the calendar month containing ``now`` (the billing period)."""
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def record_usage(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    event_type: UsageEventType,
    quantity: int = 1,
    org_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a usage event. Best-effort — a failure is logged, never raised."""
    try:
        await db.usage_events.insert_one(
            {
                "tenant_id": tenant_id,
                "org_id": org_id,
                "event_type": str(event_type),
                "quantity": quantity,
                "created_at": datetime.now(UTC),
                "metadata": metadata or {},
            }
        )
    except Exception:  # noqa: BLE001 - metering must never break the request
        log.warning("failed to record usage event", tenant_id=tenant_id, exc_info=True)


async def get_usage_summary(
    db: AsyncIOMotorDatabase, tenant_id: str, since: datetime | None = None
) -> dict[str, int]:
    """Total quantity per event type for a tenant, optionally since a timestamp."""
    match: dict[str, Any] = {"tenant_id": tenant_id}
    if since is not None:
        match["created_at"] = {"$gte": since}
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$event_type", "total": {"$sum": "$quantity"}}},
    ]
    rows = await db.usage_events.aggregate(pipeline).to_list(100)
    return {row["_id"]: int(row["total"]) for row in rows}
