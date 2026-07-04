"""Subscription plan catalog.

Plans are **product configuration defined in code**, not stored in Mongo: each plan
carries the monthly quota limits that gate usage (see ``models/usage.py`` for the
matching event types). An org's active plan is chosen by its subscription
(``db/subscriptions.py``); orgs without a subscription fall back to the FREE plan,
so plans are additive over the existing tenancy.
"""

from enum import StrEnum

from pydantic import BaseModel


class PlanTier(StrEnum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"


class PlanLimits(BaseModel):
    """Monthly quota per usage event type. ``None`` means unlimited.

    Field names mirror ``UsageEventType`` values so a limit can be looked up by the
    event type string via :func:`get_limit`.
    """

    ingest: int | None = None
    search: int | None = None
    graph_build: int | None = None


class Plan(BaseModel):
    tier: PlanTier
    name: str
    price_cents: int  # monthly price in USD cents
    limits: PlanLimits


PLAN_CATALOG: dict[PlanTier, Plan] = {
    PlanTier.FREE: Plan(
        tier=PlanTier.FREE,
        name="Free",
        price_cents=0,
        limits=PlanLimits(ingest=100, search=1000, graph_build=50),
    ),
    PlanTier.STARTER: Plan(
        tier=PlanTier.STARTER,
        name="Starter",
        price_cents=2900,
        limits=PlanLimits(ingest=2000, search=50000, graph_build=1000),
    ),
    PlanTier.PRO: Plan(
        tier=PlanTier.PRO,
        name="Pro",
        price_cents=9900,
        limits=PlanLimits(ingest=None, search=None, graph_build=None),
    ),
}

DEFAULT_PLAN_TIER = PlanTier.FREE


def get_plan(tier: PlanTier | str) -> Plan:
    """Return the catalog plan for a tier, defaulting to FREE for an unknown tier."""
    try:
        return PLAN_CATALOG[PlanTier(tier)]
    except (ValueError, KeyError):
        return PLAN_CATALOG[DEFAULT_PLAN_TIER]


def get_limit(plan: Plan, event_type: str) -> int | None:
    """Monthly limit for a usage event type under ``plan`` (``None`` = unlimited)."""
    return getattr(plan.limits, event_type, None)
