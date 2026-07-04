"""Tests for docingest.db.organizations.

`slugify` is a pure unit test. The rest are integration tests that require MongoDB
at localhost:27017 (or MONGODB_URI), matching the pattern in test_graph_store.py.
"""

from __future__ import annotations

import os

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.db.organizations import (
    add_membership,
    create_organization,
    ensure_org_indexes,
    get_membership,
    get_organization,
    get_organization_by_slug,
    list_org_members,
    list_user_organizations,
    remove_membership,
    slugify,
    update_member_role,
)
from docingest.models.organization import OrgRole

TEST_DB_NAME = "docingest_test_orgs"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")


# --- pure unit tests (no MongoDB) ---


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("My Org", "my-org"),
        ("Hello!!World", "hello-world"),
        ("  Acme, Inc.  ", "acme-inc"),
        ("A_B", "a-b"),
        ("", "org"),
        ("123", "123"),
    ],
)
def test_slugify(name, expected):
    assert slugify(name) == expected


# --- integration tests (MongoDB) ---


@pytest.fixture()
async def db():
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_org_indexes(database)
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


async def test_create_organization_adds_owner_membership(db):
    org = await create_organization(db, "Acme", owner_user_id="user-1")
    assert org["name"] == "Acme"
    assert org["slug"] == "acme"
    org_id = str(org["_id"])

    membership = await get_membership(db, org_id, "user-1")
    assert membership is not None
    assert membership["role"] == OrgRole.OWNER


async def test_slug_uniqueness(db):
    a = await create_organization(db, "Acme", owner_user_id="u1")
    b = await create_organization(db, "Acme", owner_user_id="u2")
    assert a["slug"] == "acme"
    assert b["slug"] == "acme-2"


async def test_explicit_slug_and_lookup(db):
    org = await create_organization(db, "Widgets", owner_user_id="u1", slug="widgets-co")
    assert org["slug"] == "widgets-co"
    found = await get_organization_by_slug(db, "widgets-co")
    assert found is not None
    assert str(found["_id"]) == str(org["_id"])
    assert await get_organization(db, str(org["_id"])) is not None


async def test_membership_lifecycle(db):
    org = await create_organization(db, "Acme", owner_user_id="owner")
    org_id = str(org["_id"])

    await add_membership(db, org_id, "member-1", OrgRole.MEMBER)
    m = await get_membership(db, org_id, "member-1")
    assert m["role"] == OrgRole.MEMBER

    # Idempotent: re-adding updates the role, does not duplicate.
    await add_membership(db, org_id, "member-1", OrgRole.ADMIN)
    members = await list_org_members(db, org_id)
    assert len([x for x in members if x["user_id"] == "member-1"]) == 1
    assert (await get_membership(db, org_id, "member-1"))["role"] == OrgRole.ADMIN

    assert await update_member_role(db, org_id, "member-1", OrgRole.MEMBER) is True
    assert (await get_membership(db, org_id, "member-1"))["role"] == OrgRole.MEMBER

    assert await remove_membership(db, org_id, "member-1") is True
    assert await get_membership(db, org_id, "member-1") is None


async def test_list_user_organizations_with_roles(db):
    org1 = await create_organization(db, "First", owner_user_id="alice")
    org2 = await create_organization(db, "Second", owner_user_id="bob")
    await add_membership(db, str(org2["_id"]), "alice", OrgRole.MEMBER)

    orgs = await list_user_organizations(db, "alice")
    by_id = {str(o["_id"]): o["role"] for o in orgs}
    assert by_id[str(org1["_id"])] == OrgRole.OWNER
    assert by_id[str(org2["_id"])] == OrgRole.MEMBER
    assert len(orgs) == 2

    assert await list_user_organizations(db, "nobody") == []
