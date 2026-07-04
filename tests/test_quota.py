"""Tests for docingest.services.quota.

QuotaCheck arithmetic and the flag-off no-op are pure unit tests. Resolving the
plan + current-month usage and the 402 enforcement are integration tests requiring
MongoDB at localhost:27017, matching test_usage.py / test_plans.py.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.db.subscriptions import ensure_subscription_indexes, set_subscription
from docingest.db.usage import ensure_usage_indexes, record_usage
from docingest.models.plan import PlanTier
from docingest.models.usage import UsageEventType
from docingest.services import quota as quota_svc
from docingest.services.quota import QuotaCheck, enforce_quota, get_quota_check

TEST_DB_NAME = "docingest_test_quota"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")


# --- pure unit tests (no Mongo) ---


def test_quota_check_allowed_under_limit():
    c = QuotaCheck("ingest", limit=100, used=99)
    assert c.allowed is True
    assert c.remaining == 1


def test_quota_check_blocked_at_limit():
    c = QuotaCheck("ingest", limit=100, used=100)
    assert c.allowed is False
    assert c.remaining == 0


def test_quota_check_remaining_never_negative():
    c = QuotaCheck("ingest", limit=100, used=150)
    assert c.allowed is False
    assert c.remaining == 0


def test_quota_check_unlimited():
    c = QuotaCheck("ingest", limit=None, used=10_000)
    assert c.allowed is True
    assert c.remaining is None


async def test_enforce_quota_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(quota_svc.settings, "quota_enforcement_enabled", False)

    # Flag off: returns before touching the db, so a broken db must not matter.
    class BadDB:
        def __getattr__(self, name):
            raise AssertionError("db should not be accessed when enforcement is off")

    await enforce_quota(BadDB(), "t1", UsageEventType.INGEST)


# --- integration tests (Mongo) ---


@pytest.fixture()
async def db():
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_usage_indexes(database)
    await ensure_subscription_indexes(database)
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


async def test_get_quota_check_uses_free_plan_by_default(db):
    # No subscription → FREE plan (ingest limit 100).
    for _ in range(3):
        await record_usage(db, "t1", UsageEventType.INGEST)
    check = await get_quota_check(db, "t1", UsageEventType.INGEST)
    assert check.limit == 100
    assert check.used == 3
    assert check.allowed is True


async def test_get_quota_check_unlimited_on_pro(db):
    await set_subscription(db, "t1", PlanTier.PRO)
    await record_usage(db, "t1", UsageEventType.INGEST, quantity=5000)
    check = await get_quota_check(db, "t1", UsageEventType.INGEST)
    assert check.limit is None
    assert check.allowed is True


async def test_enforce_quota_raises_402_over_limit(db, monkeypatch):
    monkeypatch.setattr(quota_svc.settings, "quota_enforcement_enabled", True)
    # FREE search limit is 1000 — record exactly that, so the next is blocked.
    await record_usage(db, "t1", UsageEventType.SEARCH, quantity=1000)
    with pytest.raises(HTTPException) as exc:
        await enforce_quota(db, "t1", UsageEventType.SEARCH)
    assert exc.value.status_code == 402


async def test_enforce_quota_allows_under_limit(db, monkeypatch):
    monkeypatch.setattr(quota_svc.settings, "quota_enforcement_enabled", True)
    await record_usage(db, "t1", UsageEventType.SEARCH, quantity=999)
    # Under the FREE limit of 1000 — must not raise.
    await enforce_quota(db, "t1", UsageEventType.SEARCH)
