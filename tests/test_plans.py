"""Tests for the plan catalog, subscription storage, and subscription routes.

The catalog helpers are pure unit tests. Subscription CRUD + the routes are
integration tests requiring MongoDB at localhost:27017, matching test_usage.py.
"""

from __future__ import annotations

import os

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.api.routes import plans as plans_routes
from docingest.db.subscriptions import (
    ensure_subscription_indexes,
    get_plan_for_tenant,
    get_subscription,
    set_subscription,
)
from docingest.models.plan import (
    DEFAULT_PLAN_TIER,
    PLAN_CATALOG,
    PlanTier,
    get_limit,
    get_plan,
)
from docingest.models.subscription import (
    SubscriptionStatus,
    UpdateSubscriptionRequest,
)

TEST_DB_NAME = "docingest_test_plans"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")


# --- pure unit tests (no Mongo) ---


def test_catalog_covers_every_tier():
    assert set(PLAN_CATALOG) == set(PlanTier)


def test_get_plan_known_tier():
    assert get_plan(PlanTier.STARTER).tier == PlanTier.STARTER
    assert get_plan("pro").tier == PlanTier.PRO


def test_get_plan_unknown_tier_defaults_to_free():
    assert get_plan("enterprise-does-not-exist").tier == DEFAULT_PLAN_TIER
    assert DEFAULT_PLAN_TIER == PlanTier.FREE


def test_get_limit_reads_per_event_type():
    free = get_plan(PlanTier.FREE)
    assert get_limit(free, "ingest") == 100
    assert get_limit(free, "search") == 1000
    # Pro is unlimited; an unknown event type is treated as unlimited too.
    assert get_limit(get_plan(PlanTier.PRO), "ingest") is None
    assert get_limit(free, "not_a_metric") is None


# --- integration tests (Mongo) ---


@pytest.fixture()
async def db(monkeypatch):
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_subscription_indexes(database)

    async def _get_db():
        return database

    monkeypatch.setattr(plans_routes, "get_db", _get_db)
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


async def test_default_plan_is_free_without_subscription(db):
    assert (await get_plan_for_tenant(db, "t-none")).tier == PlanTier.FREE


async def test_set_and_resolve_subscription(db):
    sub = await set_subscription(db, "t1", PlanTier.STARTER)
    assert sub["plan_tier"] == "starter"
    assert sub["status"] == "active"
    assert (await get_plan_for_tenant(db, "t1")).tier == PlanTier.STARTER


async def test_set_subscription_is_idempotent_per_tenant(db):
    first = await set_subscription(db, "t1", PlanTier.STARTER)
    second = await set_subscription(db, "t1", PlanTier.PRO)
    # Same document updated in place; created_at preserved, plan swapped.
    assert second["created_at"] == first["created_at"]
    assert (await get_plan_for_tenant(db, "t1")).tier == PlanTier.PRO


async def test_canceled_subscription_falls_back_to_free(db):
    await set_subscription(db, "t1", PlanTier.PRO, status=SubscriptionStatus.CANCELED)
    assert (await get_plan_for_tenant(db, "t1")).tier == PlanTier.FREE


def _org(tenant_id: str, role: str = "owner") -> dict:
    return {"org_id": tenant_id, "user_id": "u1", "role": role}


async def test_route_get_subscription_defaults_to_free(db):
    resp = await plans_routes.get_my_subscription(_org("t-fresh"))
    assert resp.plan.tier == PlanTier.FREE
    assert resp.status == SubscriptionStatus.ACTIVE
    assert resp.updated_at is None


async def test_route_update_then_get_subscription(db):
    updated = await plans_routes.update_my_subscription(
        UpdateSubscriptionRequest(plan_tier=PlanTier.STARTER), _org("t2")
    )
    assert updated.plan.tier == PlanTier.STARTER
    assert updated.updated_at is not None

    fetched = await plans_routes.get_my_subscription(_org("t2"))
    assert fetched.plan.tier == PlanTier.STARTER
    assert await get_subscription(db, "t2") is not None


async def test_route_list_plans_returns_catalog(db):
    catalog = await plans_routes.list_plans(user={"user_id": "u1"})
    assert {p.tier for p in catalog} == set(PlanTier)
