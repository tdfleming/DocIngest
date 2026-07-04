"""MongoDB storage for organizations and memberships.

Collections: ``organizations``, ``organization_memberships``. An organization's
string id doubles as the ``tenant_id`` for all downstream data isolation.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from docingest.models.organization import OrgRole


async def ensure_org_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create org/membership indexes. Unique slug; one membership per (org, user)."""
    await db.organizations.create_index("slug", unique=True)
    await db.organizations.create_index("owner_user_id")
    await db.organization_memberships.create_index(
        [("org_id", 1), ("user_id", 1)], unique=True
    )
    await db.organization_memberships.create_index("user_id")
    await db.organization_memberships.create_index("org_id")


def slugify(name: str) -> str:
    """Turn a display name into a url-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


async def _unique_slug(db: AsyncIOMotorDatabase, base: str) -> str:
    """Return ``base`` or ``base-2``/``base-3``/… so the slug is unused."""
    candidate = base
    i = 2
    while await db.organizations.find_one({"slug": candidate}):
        candidate = f"{base}-{i}"
        i += 1
    return candidate


async def create_organization(
    db: AsyncIOMotorDatabase,
    name: str,
    owner_user_id: str,
    slug: str | None = None,
) -> dict:
    """Create an organization and add the owner as an OWNER member.

    The org's string id becomes the tenant_id used by all data isolation.
    """
    base = slug or slugify(name)
    doc: dict[str, Any] = {
        "name": name,
        "slug": await _unique_slug(db, base),
        "owner_user_id": owner_user_id,
        "created_at": datetime.now(UTC),
    }
    try:
        result = await db.organizations.insert_one(doc)
    except DuplicateKeyError:
        # Rare slug race — fall back to a guaranteed-unique suffix.
        doc["slug"] = f"{base}-{uuid.uuid4().hex[:6]}"
        result = await db.organizations.insert_one(doc)
    doc["_id"] = result.inserted_id
    await add_membership(db, str(result.inserted_id), owner_user_id, OrgRole.OWNER)
    return doc


async def get_organization(db: AsyncIOMotorDatabase, org_id: str) -> dict | None:
    return await db.organizations.find_one({"_id": ObjectId(org_id)})


async def get_organization_by_slug(db: AsyncIOMotorDatabase, slug: str) -> dict | None:
    return await db.organizations.find_one({"slug": slug})


async def add_membership(
    db: AsyncIOMotorDatabase, org_id: str, user_id: str, role: OrgRole
) -> dict:
    """Add or update a user's membership in an org (idempotent on (org, user))."""
    await db.organization_memberships.update_one(
        {"org_id": org_id, "user_id": user_id},
        {
            "$set": {"role": str(role)},
            "$setOnInsert": {"created_at": datetime.now(UTC)},
        },
        upsert=True,
    )
    return await get_membership(db, org_id, user_id)


async def get_membership(
    db: AsyncIOMotorDatabase, org_id: str, user_id: str
) -> dict | None:
    return await db.organization_memberships.find_one(
        {"org_id": org_id, "user_id": user_id}
    )


async def list_user_organizations(db: AsyncIOMotorDatabase, user_id: str) -> list[dict]:
    """Return orgs the user belongs to, each annotated with the user's role."""
    memberships = await db.organization_memberships.find({"user_id": user_id}).to_list(1000)
    by_role = {m["org_id"]: m["role"] for m in memberships}
    if not by_role:
        return []
    ids = [ObjectId(oid) for oid in by_role]
    orgs = await db.organizations.find({"_id": {"$in": ids}}).to_list(1000)
    for org in orgs:
        org["role"] = by_role.get(str(org["_id"]))
    return orgs


async def list_org_members(db: AsyncIOMotorDatabase, org_id: str) -> list[dict]:
    return await db.organization_memberships.find({"org_id": org_id}).to_list(1000)


async def update_member_role(
    db: AsyncIOMotorDatabase, org_id: str, user_id: str, role: OrgRole
) -> bool:
    result = await db.organization_memberships.update_one(
        {"org_id": org_id, "user_id": user_id}, {"$set": {"role": str(role)}}
    )
    return result.matched_count > 0


async def remove_membership(db: AsyncIOMotorDatabase, org_id: str, user_id: str) -> bool:
    result = await db.organization_memberships.delete_one(
        {"org_id": org_id, "user_id": user_id}
    )
    return result.deleted_count > 0
