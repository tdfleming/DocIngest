"""Tests for Stripe billing: signing/encoding/mapping (pure) + webhook sync (Mongo).

The pure helpers run locally. handle_stripe_event drives the subscription row and is
an integration test requiring MongoDB at localhost:27017, matching test_usage.py.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.api.routes import billing
from docingest.db.subscriptions import (
    ensure_subscription_indexes,
    get_subscription,
    set_subscription,
)
from docingest.models.plan import PlanTier
from docingest.models.subscription import SubscriptionStatus
from docingest.services import stripe_client

TEST_DB_NAME = "docingest_test_stripe"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")


# --- pure unit tests (no Mongo, no network) ---


def _sign(payload: bytes, secret: str, ts: int = 1_700_000_000) -> str:
    signed = f"{ts}".encode() + b"." + payload
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_verify_signature_roundtrip():
    payload = b'{"hello":"world"}'
    header = _sign(payload, "whsec_test")
    assert stripe_client.verify_webhook_signature(payload, header, "whsec_test", now=1_700_000_010)


def test_verify_signature_rejects_tampered_payload():
    header = _sign(b'{"amount":100}', "whsec_test")
    assert not stripe_client.verify_webhook_signature(
        b'{"amount":999}', header, "whsec_test", now=1_700_000_010
    )


def test_verify_signature_rejects_wrong_secret():
    payload = b'{"a":1}'
    header = _sign(payload, "whsec_real")
    assert not stripe_client.verify_webhook_signature(
        payload, header, "whsec_wrong", now=1_700_000_010
    )


def test_verify_signature_rejects_stale_timestamp():
    payload = b'{"a":1}'
    header = _sign(payload, "whsec_test", ts=1_700_000_000)
    # 10 minutes later, default tolerance 300s -> rejected.
    assert not stripe_client.verify_webhook_signature(
        payload, header, "whsec_test", now=1_700_000_600
    )


def test_construct_event_parses_after_verify():
    payload = json.dumps({"type": "checkout.session.completed"}).encode()
    header = _sign(payload, "whsec_test")
    event = stripe_client.construct_event(payload, header, "whsec_test", now=1_700_000_010)
    assert event["type"] == "checkout.session.completed"


def test_construct_event_raises_on_bad_signature():
    with pytest.raises(ValueError):
        stripe_client.construct_event(b"{}", "t=1,v1=deadbeef", "whsec_test", now=1)


def test_checkout_params_carry_tenant_and_price(monkeypatch):
    monkeypatch.setattr(stripe_client.settings, "stripe_checkout_success_url", "https://s")
    monkeypatch.setattr(stripe_client.settings, "stripe_checkout_cancel_url", "https://c")
    params = stripe_client.checkout_params("tenant-1", "price_123", PlanTier.PRO)
    assert params["line_items[0][price]"] == "price_123"
    assert params["client_reference_id"] == "tenant-1"
    assert params["metadata[plan_tier]"] == "pro"
    assert params["subscription_data[metadata][tenant_id]"] == "tenant-1"
    assert params["mode"] == "subscription"


def test_price_tier_mapping(monkeypatch):
    monkeypatch.setattr(stripe_client.settings, "stripe_price_starter", "price_s")
    monkeypatch.setattr(stripe_client.settings, "stripe_price_pro", "price_p")
    assert stripe_client.price_id_for_tier(PlanTier.STARTER) == "price_s"
    assert stripe_client.tier_for_price_id("price_p") == PlanTier.PRO
    assert stripe_client.tier_for_price_id("price_unknown") is None
    assert stripe_client.price_id_for_tier(PlanTier.FREE) is None


def test_map_stripe_status():
    assert stripe_client.map_stripe_status("active") == SubscriptionStatus.ACTIVE
    assert stripe_client.map_stripe_status("trialing") == SubscriptionStatus.ACTIVE
    assert stripe_client.map_stripe_status("past_due") == SubscriptionStatus.PAST_DUE
    assert stripe_client.map_stripe_status("canceled") == SubscriptionStatus.CANCELED


def test_first_price_id():
    sub = {"items": {"data": [{"price": {"id": "price_x"}}]}}
    assert stripe_client.first_price_id(sub) == "price_x"
    assert stripe_client.first_price_id({"items": {"data": []}}) is None


async def test_billing_config_reflects_flag(monkeypatch):
    monkeypatch.setattr(billing.settings, "stripe_enabled", True)
    assert (await billing.billing_config(user={"user_id": "u1"}))["enabled"] is True
    monkeypatch.setattr(billing.settings, "stripe_enabled", False)
    assert (await billing.billing_config(user={"user_id": "u1"}))["enabled"] is False


# --- integration tests (Mongo) ---


@pytest.fixture()
async def db():
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_subscription_indexes(database)
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


async def test_checkout_completed_activates_subscription(db):
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "t1",
                "customer": "cus_1",
                "subscription": "sub_1",
                "metadata": {"tenant_id": "t1", "plan_tier": "pro"},
            }
        },
    }
    await billing.handle_stripe_event(db, event)
    sub = await get_subscription(db, "t1")
    assert sub["plan_tier"] == "pro"
    assert sub["status"] == "active"
    assert sub["stripe_customer_id"] == "cus_1"


async def test_subscription_deleted_cancels_by_customer_lookup(db):
    await set_subscription(
        db, "t1", PlanTier.PRO, stripe_customer_id="cus_1", stripe_subscription_id="sub_1"
    )
    event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_1", "customer": "cus_1", "metadata": {}}},
    }
    await billing.handle_stripe_event(db, event)
    sub = await get_subscription(db, "t1")
    assert sub["status"] == "canceled"


async def test_subscription_updated_maps_status_and_price(db, monkeypatch):
    monkeypatch.setattr(stripe_client.settings, "stripe_price_starter", "price_s")
    await set_subscription(db, "t1", PlanTier.PRO, stripe_customer_id="cus_1")
    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_1",
                "status": "past_due",
                "items": {"data": [{"price": {"id": "price_s"}}]},
                "metadata": {},
            }
        },
    }
    await billing.handle_stripe_event(db, event)
    sub = await get_subscription(db, "t1")
    assert sub["status"] == "past_due"
    assert sub["plan_tier"] == "starter"


async def test_unmapped_subscription_event_is_ignored(db):
    # No matching customer and no metadata tenant id -> no-op, no crash.
    event = {
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_x", "customer": "cus_unknown", "metadata": {}}},
    }
    await billing.handle_stripe_event(db, event)
    assert await get_subscription(db, "cus_unknown") is None
