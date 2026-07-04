"""Usage route: current billing-period usage for the caller's tenant."""

from datetime import UTC, datetime

from fastapi import APIRouter

from docingest.api.auth import Tenant
from docingest.db.mongodb import get_db
from docingest.db.usage import get_usage_summary, month_start
from docingest.models.usage import UsageSummary

router = APIRouter()


@router.get("/usage")
async def get_usage(tenant: Tenant) -> UsageSummary:
    """Usage totals per event type for the current calendar month."""
    db = await get_db()
    start = month_start(datetime.now(UTC))
    events = await get_usage_summary(db, tenant["tenant_id"], since=start)
    return UsageSummary(period_start=start.isoformat(), events=events)
