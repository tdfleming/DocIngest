"""Subscription models.

A subscription links a tenant (org) to a plan tier. The persisted document lives in
Mongo (``db/subscriptions.py``); the API request/response shapes are here alongside
the domain enum. Stripe identifiers are added additively in a later slice.
"""

from enum import StrEnum

from pydantic import BaseModel

from docingest.models.plan import Plan, PlanTier


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


# --- API request/response models ---


class UpdateSubscriptionRequest(BaseModel):
    plan_tier: PlanTier


class SubscriptionResponse(BaseModel):
    plan: Plan
    status: SubscriptionStatus
    # First instant of the current billing month (aligns with usage period).
    current_period_start: str
    updated_at: str | None = None
