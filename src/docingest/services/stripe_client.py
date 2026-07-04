"""Async Stripe client + pure billing helpers.

Talks to the Stripe REST API over the shared httpx stack (the official SDK is
sync). The pure helpers — form-param building, webhook signature verification, and
plan/price mapping — are separated out so they can be unit-tested without network
or Stripe credentials. Everything here is only exercised when ``stripe_enabled``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import httpx

from docingest.config import settings
from docingest.models.plan import PlanTier
from docingest.models.subscription import SubscriptionStatus

# --- plan <-> Stripe price mapping (pure) ---


def price_id_for_tier(tier: PlanTier) -> str | None:
    """The configured Stripe Price id for a paid tier (None if unset/free)."""
    mapping = {
        PlanTier.STARTER: settings.stripe_price_starter,
        PlanTier.PRO: settings.stripe_price_pro,
    }
    return mapping.get(tier) or None


def tier_for_price_id(price_id: str | None) -> PlanTier | None:
    """Reverse-map a Stripe Price id back to a plan tier (None if unrecognized)."""
    if not price_id:
        return None
    if price_id == settings.stripe_price_starter:
        return PlanTier.STARTER
    if price_id == settings.stripe_price_pro:
        return PlanTier.PRO
    return None


def map_stripe_status(stripe_status: str) -> SubscriptionStatus:
    """Collapse a Stripe subscription status into our coarse status."""
    if stripe_status in ("active", "trialing"):
        return SubscriptionStatus.ACTIVE
    if stripe_status in ("past_due", "incomplete"):
        return SubscriptionStatus.PAST_DUE
    return SubscriptionStatus.CANCELED


def first_price_id(subscription_obj: dict) -> str | None:
    """Pull the first line item's Price id from a Stripe subscription object."""
    items = subscription_obj.get("items", {}).get("data", [])
    if items:
        return items[0].get("price", {}).get("id")
    return None


# --- Checkout params (pure) ---


def checkout_params(tenant_id: str, price_id: str, plan_tier: PlanTier) -> dict[str, str]:
    """Flat form params for a subscription Checkout session.

    ``client_reference_id`` and the metadata carry the tenant id back through the
    webhook so the subscription can be reconciled without a prior customer record.
    """
    return {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": settings.stripe_checkout_success_url,
        "cancel_url": settings.stripe_checkout_cancel_url,
        "client_reference_id": tenant_id,
        "metadata[tenant_id]": tenant_id,
        "metadata[plan_tier]": str(plan_tier),
        "subscription_data[metadata][tenant_id]": tenant_id,
        "subscription_data[metadata][plan_tier]": str(plan_tier),
    }


# --- Webhook signature verification (pure) ---


def verify_webhook_signature(
    payload: bytes,
    sig_header: str,
    secret: str,
    tolerance: int = 300,
    now: float | None = None,
) -> bool:
    """Verify a Stripe ``Stripe-Signature`` header against the raw request body.

    Stripe signs ``f"{timestamp}.{payload}"`` with HMAC-SHA256. ``now`` is injectable
    for testing; when omitted the current time is used for the tolerance window.
    """
    if not secret or not sig_header:
        return False
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    timestamp, signature = parts.get("t"), parts.get("v1")
    if not timestamp or not signature:
        return False
    signed = timestamp.encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False
    current = time.time() if now is None else now
    return abs(current - int(timestamp)) <= tolerance


def construct_event(payload: bytes, sig_header: str, secret: str, now: float | None = None) -> dict:
    """Verify the signature and parse the event JSON. Raises ValueError if invalid."""
    if not verify_webhook_signature(payload, sig_header, secret, now=now):
        raise ValueError("invalid Stripe webhook signature")
    return json.loads(payload)


# --- Stripe REST calls (network) ---


async def _post(path: str, data: dict[str, str]) -> dict:
    """POST form-encoded data to Stripe with secret-key basic auth."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            settings.stripe_api_base + path,
            data=data,
            auth=(settings.stripe_secret_key, ""),
        )
        resp.raise_for_status()
        return resp.json()


async def create_checkout_session(tenant_id: str, price_id: str, plan_tier: PlanTier) -> dict:
    """Create a subscription Checkout session; returns the Stripe session (has ``url``)."""
    return await _post("/v1/checkout/sessions", checkout_params(tenant_id, price_id, plan_tier))


async def create_portal_session(customer_id: str) -> dict:
    """Create a hosted Billing Portal session for a customer (returns ``url``)."""
    return await _post(
        "/v1/billing_portal/sessions",
        {"customer": customer_id, "return_url": settings.stripe_portal_return_url},
    )
