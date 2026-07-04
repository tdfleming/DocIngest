"""Plan quota enforcement.

Compares a tenant's current-month usage (``db/usage.py``) against the limits of its
active plan (``db/subscriptions.py`` → ``models/plan.py``) and blocks requests that
would exceed a limit.

Enforcement is gated by ``settings.quota_enforcement_enabled`` (OFF by default): a
self-hosted/OSS deployment stays unmetered, while the managed cloud turns it on so
the FREE plan's limits apply. When the flag is off, :func:`enforce_quota` is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from docingest.config import settings
from docingest.db.subscriptions import get_plan_for_tenant
from docingest.db.usage import get_usage_summary, month_start
from docingest.models.plan import get_limit
from docingest.models.usage import UsageEventType


@dataclass
class QuotaCheck:
    """The quota position for one event type in the current billing month."""

    event_type: str
    limit: int | None  # None = unlimited
    used: int

    @property
    def allowed(self) -> bool:
        """Whether one more event of this type is within the plan limit."""
        return self.limit is None or self.used < self.limit

    @property
    def remaining(self) -> int | None:
        """Events left this month (None = unlimited)."""
        return None if self.limit is None else max(0, self.limit - self.used)


async def get_quota_check(
    db: AsyncIOMotorDatabase, tenant_id: str, event_type: UsageEventType
) -> QuotaCheck:
    """Resolve the tenant's plan limit and current-month usage for ``event_type``."""
    plan = await get_plan_for_tenant(db, tenant_id)
    limit = get_limit(plan, str(event_type))
    if limit is None:
        return QuotaCheck(str(event_type), None, 0)
    since = month_start(datetime.now(UTC))
    usage = await get_usage_summary(db, tenant_id, since=since)
    return QuotaCheck(str(event_type), limit, usage.get(str(event_type), 0))


async def enforce_quota(
    db: AsyncIOMotorDatabase, tenant_id: str, event_type: UsageEventType
) -> None:
    """Raise 402 if the tenant has hit its plan limit for ``event_type`` this month.

    No-op when ``quota_enforcement_enabled`` is off.
    """
    if not settings.quota_enforcement_enabled:
        return
    check = await get_quota_check(db, tenant_id, event_type)
    if not check.allowed:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Monthly {event_type} quota exceeded ({check.used}/{check.limit}). "
                "Upgrade your plan to continue."
            ),
        )
