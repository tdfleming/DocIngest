"""Tests for organization management routes and org-context dependencies.

resolve_org / require_org_role are unit-tested (mocked). The management flow is
an integration test requiring MongoDB at localhost:27017.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.api import auth as auth_core
from docingest.api.routes import organizations as orgs_routes
from docingest.db.mongodb import ensure_indexes
from docingest.db.organizations import ensure_org_indexes, get_membership
from docingest.models.organization import (
    AddMemberRequest,
    CreateOrganizationRequest,
    OrgRole,
    UpdateMemberRequest,
)

TEST_DB_NAME = "docingest_test_org_routes"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")


# --- unit tests (no Mongo) ---


async def test_resolve_org_403_without_org_in_token():
    with pytest.raises(HTTPException) as exc:
        await auth_core.resolve_org(user={"user_id": "u", "org_id": None})
    assert exc.value.status_code == 403


async def test_resolve_org_403_when_not_a_member(monkeypatch):
    async def _get_db():
        return object()

    async def _no_membership(db, org_id, user_id):
        return None

    monkeypatch.setattr(auth_core, "get_db", _get_db)
    monkeypatch.setattr(auth_core, "get_membership", _no_membership)
    with pytest.raises(HTTPException) as exc:
        await auth_core.resolve_org(user={"user_id": "u", "org_id": "o1"})
    assert exc.value.status_code == 403


async def test_resolve_org_returns_role(monkeypatch):
    async def _get_db():
        return object()

    async def _membership(db, org_id, user_id):
        return {"org_id": org_id, "user_id": user_id, "role": "admin"}

    monkeypatch.setattr(auth_core, "get_db", _get_db)
    monkeypatch.setattr(auth_core, "get_membership", _membership)
    org = await auth_core.resolve_org(user={"user_id": "u", "org_id": "o1"})
    assert org["role"] == "admin"


async def test_require_org_role_allows_and_denies():
    dep = auth_core.require_org_role(OrgRole.OWNER, OrgRole.ADMIN)
    assert (await dep(org={"role": "admin"}))["role"] == "admin"
    with pytest.raises(HTTPException) as exc:
        await dep(org={"role": "member"})
    assert exc.value.status_code == 403


# --- integration tests (Mongo) ---


@pytest.fixture()
async def db(monkeypatch):
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_indexes(database)
    await ensure_org_indexes(database)

    async def _get_db():
        return database

    monkeypatch.setattr(orgs_routes, "get_db", _get_db)
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


async def _make_user(db, username: str) -> str:
    result = await db.users.insert_one(
        {"username": username, "password_hash": "x", "role": "viewer",
         "created_at": datetime.now(UTC)}
    )
    return str(result.inserted_id)


def _actor(user_id: str, username: str) -> dict:
    return {"user_id": user_id, "username": username, "role": "viewer", "org_id": None}


async def test_org_management_flow(db):
    owner_id = await _make_user(db, "owner")
    bob_id = await _make_user(db, "bob")
    owner = _actor(owner_id, "owner")

    # create org -> owner
    org = await orgs_routes.create_org(CreateOrganizationRequest(name="Acme"), owner)
    assert org.role == OrgRole.OWNER
    org_id = org.id

    # add bob as member
    added = await orgs_routes.add_member(org_id, AddMemberRequest(username="bob"), owner)
    assert added.username == "bob"
    assert added.role == OrgRole.MEMBER

    # list members includes usernames
    members = await orgs_routes.get_members(org_id, owner)
    assert {m.username for m in members} == {"owner", "bob"}

    # a plain member cannot manage
    bob = _actor(bob_id, "bob")
    with pytest.raises(HTTPException) as exc:
        await orgs_routes.add_member(org_id, AddMemberRequest(username="owner"), bob)
    assert exc.value.status_code == 403

    # promote bob to admin
    await orgs_routes.change_member_role(
        org_id, bob_id, UpdateMemberRequest(role=OrgRole.ADMIN), owner
    )
    assert (await get_membership(db, org_id, bob_id))["role"] == OrgRole.ADMIN

    # cannot demote the last owner
    with pytest.raises(HTTPException) as exc:
        await orgs_routes.change_member_role(
            org_id, owner_id, UpdateMemberRequest(role=OrgRole.MEMBER), owner
        )
    assert exc.value.status_code == 400

    # cannot remove the last owner
    with pytest.raises(HTTPException) as exc:
        await orgs_routes.remove_member(org_id, owner_id, owner)
    assert exc.value.status_code == 400

    # remove bob
    result = await orgs_routes.remove_member(org_id, bob_id, owner)
    assert result["status"] == "removed"
    assert await get_membership(db, org_id, bob_id) is None


async def test_add_member_unknown_user_404(db):
    owner_id = await _make_user(db, "owner")
    owner = _actor(owner_id, "owner")
    org = await orgs_routes.create_org(CreateOrganizationRequest(name="Acme"), owner)
    with pytest.raises(HTTPException) as exc:
        await orgs_routes.add_member(org.id, AddMemberRequest(username="ghost"), owner)
    assert exc.value.status_code == 404
