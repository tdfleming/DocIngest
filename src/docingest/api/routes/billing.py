"""Stripe billing routes: Checkout, hosted Billing Portal, and webhook sync.

All endpoints are gated by ``settings.stripe_enabled`` (404 when off). Paid plans
are purchased through Checkout; Stripe **webhooks are the source of truth** and drive
the local subscription row via :func:`handle_stripe_event`. The tenant id is carried
on ``client_reference_id`` + metadata so events reconcile without a prior customer.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from docingest.api.auth import CurrentUser, OrgManager
from docingest.config import settings
from docingest.db.mongodb import get_db
from docingest.db.subscriptions import (
    get_subscription,
    get_subscription_by_stripe_customer,
    set_subscription,
)
from docingest.models.plan import PlanTier
from docingest.models.subscription import SubscriptionStatus
from docingest.services import stripe_client

router = APIRouter(prefix="/billing")
log = structlog.get_logger()


class CheckoutRequest(BaseModel):
    plan_tier: PlanTier


def _require_stripe() -> None:
    if not settings.stripe_enabled:
        raise HTTPException(status_code=404, detail="Billing is not enabled")


@router.get("/config")
async def billing_config(user: CurrentUser):
    """Whether Stripe billing is enabled — lets the UI hide Checkout/Portal actions."""
    return {"enabled": settings.stripe_enabled}


@router.post("/checkout")
async def create_checkout(body: CheckoutRequest, org: OrgManager):
    """Start a Checkout session to upgrade the org to a paid plan. Requires OWNER/ADMIN."""
    _require_stripe()
    if body.plan_tier == PlanTier.FREE:
        raise HTTPException(status_code=400, detail="Checkout is only for paid plans")
    price_id = stripe_client.price_id_for_tier(body.plan_tier)
    if not price_id:
        raise HTTPException(
            status_code=400, detail=f"No Stripe price configured for plan: {body.plan_tier}"
        )
    session = await stripe_client.create_checkout_session(org["org_id"], price_id, body.plan_tier)
    return {"checkout_url": session["url"], "session_id": session["id"]}


@router.post("/portal")
async def create_portal(org: OrgManager):
    """Open the hosted Billing Portal to manage/cancel the plan. Requires OWNER/ADMIN."""
    _require_stripe()
    db = await get_db()
    sub = await get_subscription(db, org["org_id"])
    customer_id = (sub or {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer for this organization")
    session = await stripe_client.create_portal_session(customer_id)
    return {"portal_url": session["url"]}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Receive Stripe events (unauthenticated; verified by signature)."""
    _require_stripe()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe_client.construct_event(payload, sig, settings.stripe_webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from None
    db = await get_db()
    await handle_stripe_event(db, event)
    return {"received": True}


async def handle_stripe_event(db, event: dict) -> None:
    """Apply a verified Stripe event to the tenant's subscription row.

    Handles checkout completion and subscription updates/cancellations; other event
    types are ignored. Idempotent — safe under Stripe's at-least-once redelivery.
    """
    etype = event.get("type")
    obj = event.get("data", {}).get("object", {})
    metadata = obj.get("metadata", {}) or {}

    if etype == "checkout.session.completed":
        tenant_id = obj.get("client_reference_id") or metadata.get("tenant_id")
        if not tenant_id:
            log.warning("checkout.session.completed without tenant id")
            return
        tier = metadata.get("plan_tier")
        await set_subscription(
            db,
            tenant_id,
            PlanTier(tier) if tier else PlanTier.STARTER,
            status=SubscriptionStatus.ACTIVE,
            stripe_customer_id=obj.get("customer"),
            stripe_subscription_id=obj.get("subscription"),
        )
        return

    if etype in ("customer.subscription.updated", "customer.subscription.deleted"):
        sub = None
        customer_id = obj.get("customer")
        if customer_id:
            sub = await get_subscription_by_stripe_customer(db, customer_id)
        tenant_id = sub["tenant_id"] if sub else metadata.get("tenant_id")
        if not tenant_id:
            log.warning("subscription event unmapped to a tenant", event_type=etype)
            return
        current_tier = PlanTier(sub["plan_tier"]) if sub else PlanTier.FREE
        if etype == "customer.subscription.deleted":
            status, tier = SubscriptionStatus.CANCELED, current_tier
        else:
            status = stripe_client.map_stripe_status(obj.get("status", ""))
            mapped = stripe_client.tier_for_price_id(stripe_client.first_price_id(obj))
            tier = mapped or current_tier
        await set_subscription(
            db, tenant_id, tier, status=status, stripe_subscription_id=obj.get("id")
        )
