"""MongoDB storage for org subscriptions.

Collection: ``subscriptions`` (one per tenant). A subscription links a tenant to a
plan tier; orgs without a subscription default to the FREE plan, so subscriptions
are additive — existing tenants keep working unchanged. A tenant's string id is its
org id, so ``tenant_id`` is the single key here (no separate org column).
"""

from __future__ import annotations

from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from docingest.models.plan import DEFAULT_PLAN_TIER, Plan, PlanTier, get_plan
from docingest.models.subscription import SubscriptionStatus


async def ensure_subscription_indexes(db: AsyncIOMotorDatabase) -> None:
    """One subscription per tenant."""
    await db.subscriptions.create_index("tenant_id", unique=True)


async def get_subscription(db: AsyncIOMotorDatabase, tenant_id: str) -> dict | None:
    return await db.subscriptions.find_one({"tenant_id": tenant_id})


async def set_subscription(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    plan_tier: PlanTier,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> dict:
    """Create or update a tenant's subscription (idempotent on ``tenant_id``)."""
    now = datetime.now(UTC)
    await db.subscriptions.update_one(
        {"tenant_id": tenant_id},
        {
            "$set": {
                "plan_tier": str(plan_tier),
                "status": str(status),
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return await get_subscription(db, tenant_id)


async def get_plan_for_tenant(db: AsyncIOMotorDatabase, tenant_id: str) -> Plan:
    """Resolve a tenant's active plan, defaulting to FREE.

    A missing or non-active (e.g. canceled) subscription resolves to the FREE plan,
    which is what quota enforcement reads.
    """
    sub = await get_subscription(db, tenant_id)
    if not sub or sub.get("status") != SubscriptionStatus.ACTIVE:
        return get_plan(DEFAULT_PLAN_TIER)
    return get_plan(sub["plan_tier"])
