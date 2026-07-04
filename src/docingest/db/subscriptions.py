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
    """One subscription per tenant; look up by Stripe customer for webhooks."""
    await db.subscriptions.create_index("tenant_id", unique=True)
    await db.subscriptions.create_index("stripe_customer_id", sparse=True)


async def get_subscription(db: AsyncIOMotorDatabase, tenant_id: str) -> dict | None:
    return await db.subscriptions.find_one({"tenant_id": tenant_id})


async def get_subscription_by_stripe_customer(
    db: AsyncIOMotorDatabase, customer_id: str
) -> dict | None:
    return await db.subscriptions.find_one({"stripe_customer_id": customer_id})


async def set_subscription(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    plan_tier: PlanTier,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> dict:
    """Create or update a tenant's subscription (idempotent on ``tenant_id``).

    Stripe identifiers are only written when provided, so a plain plan change never
    clears an existing Stripe link.
    """
    now = datetime.now(UTC)
    set_fields: dict = {
        "plan_tier": str(plan_tier),
        "status": str(status),
        "updated_at": now,
    }
    if stripe_customer_id is not None:
        set_fields["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id is not None:
        set_fields["stripe_subscription_id"] = stripe_subscription_id
    await db.subscriptions.update_one(
        {"tenant_id": tenant_id},
        {"$set": set_fields, "$setOnInsert": {"created_at": now}},
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
