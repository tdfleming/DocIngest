"""Tests for docingest.db.usage.

month_start and the best-effort guarantee are pure. Aggregation is an
integration test requiring MongoDB at localhost:27017.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.db.usage import (
    ensure_usage_indexes,
    get_usage_summary,
    month_start,
    record_usage,
)
from docingest.models.usage import UsageEventType

TEST_DB_NAME = "docingest_test_usage"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")


# --- unit tests (no Mongo) ---


def test_month_start_truncates_to_first_of_month():
    dt = datetime(2026, 7, 15, 13, 30, 45, 123, tzinfo=UTC)
    assert month_start(dt) == datetime(2026, 7, 1, 0, 0, 0, 0, tzinfo=UTC)


async def test_record_usage_never_raises():
    class BadDB:
        @property
        def usage_events(self):
            raise RuntimeError("boom")

    # Best-effort: a broken db must not propagate an error into the request path.
    await record_usage(BadDB(), "t1", UsageEventType.SEARCH)


# --- integration tests (Mongo) ---


@pytest.fixture()
async def db():
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_usage_indexes(database)
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


async def test_record_and_summarize_by_type(db):
    await record_usage(db, "t1", UsageEventType.INGEST)
    await record_usage(db, "t1", UsageEventType.INGEST, quantity=3)
    await record_usage(db, "t1", UsageEventType.SEARCH)
    await record_usage(db, "t2", UsageEventType.SEARCH)  # different tenant, excluded

    assert await get_usage_summary(db, "t1") == {"ingest": 4, "search": 1}


async def test_summary_respects_since_filter(db):
    await record_usage(db, "t1", UsageEventType.SEARCH)
    future = datetime.now(UTC) + timedelta(days=1)
    past = datetime.now(UTC) - timedelta(days=1)
    assert await get_usage_summary(db, "t1", since=future) == {}
    assert await get_usage_summary(db, "t1", since=past) == {"search": 1}
