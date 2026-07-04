"""Plan catalog & subscription routes (JWT-authenticated).

``GET /v1/plans`` exposes the static plan catalog. ``GET/PUT /v1/subscription`` read
and change the active org's plan. An org's id doubles as its ``tenant_id``, so the
subscription is keyed by ``org["org_id"]``.

Note: changing to a paid tier here is provisional — it takes effect immediately with
no payment. The Stripe slice routes paid upgrades through Checkout before activating.
"""

from datetime import UTC, datetime

from fastapi import APIRouter

from docingest.api.auth import CurrentOrg, CurrentUser, OrgManager
from docingest.db.mongodb import get_db
from docingest.db.subscriptions import (
    get_plan_for_tenant,
    get_subscription,
    set_subscription,
)
from docingest.db.usage import month_start
from docingest.models.plan import PLAN_CATALOG, Plan
from docingest.models.subscription import (
    SubscriptionResponse,
    SubscriptionStatus,
    UpdateSubscriptionRequest,
)

router = APIRouter()


@router.get("/plans")
async def list_plans(user: CurrentUser) -> list[Plan]:
    """The plan catalog: limits and pricing for every tier."""
    return list(PLAN_CATALOG.values())


@router.get("/subscription")
async def get_my_subscription(org: CurrentOrg) -> SubscriptionResponse:
    """The active org's subscription (defaults to the FREE plan)."""
    db = await get_db()
    sub = await get_subscription(db, org["org_id"])
    plan = await get_plan_for_tenant(db, org["org_id"])
    status = sub["status"] if sub else SubscriptionStatus.ACTIVE
    updated_at = sub["updated_at"].isoformat() if sub and sub.get("updated_at") else None
    return SubscriptionResponse(
        plan=plan,
        status=status,
        current_period_start=month_start(datetime.now(UTC)).isoformat(),
        updated_at=updated_at,
    )


@router.put("/subscription")
async def update_my_subscription(
    body: UpdateSubscriptionRequest, org: OrgManager
) -> SubscriptionResponse:
    """Change the active org's plan. Requires OWNER/ADMIN."""
    db = await get_db()
    sub = await set_subscription(db, org["org_id"], body.plan_tier)
    plan = await get_plan_for_tenant(db, org["org_id"])
    return SubscriptionResponse(
        plan=plan,
        status=sub["status"],
        current_period_start=month_start(datetime.now(UTC)).isoformat(),
        updated_at=sub["updated_at"].isoformat(),
    )
