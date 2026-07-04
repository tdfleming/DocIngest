"""Tests for self-serve signup and org-aware JWTs.

Token/resolve tests are pure (no Mongo). The signup endpoint tests are
integration tests requiring MongoDB at localhost:27017 (or MONGODB_URI).
"""

from __future__ import annotations

import os

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.api import auth as auth_core
from docingest.api.routes import auth as auth_routes
from docingest.config import settings
from docingest.db.mongodb import ensure_indexes
from docingest.db.organizations import ensure_org_indexes, get_membership
from docingest.models.organization import OrgRole
from docingest.models.user import LoginRequest, SignupRequest

TEST_DB_NAME = "docingest_test_auth_signup"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")


def _decode(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


# --- unit tests (no Mongo) ---


def test_token_includes_org_id():
    token = auth_core.create_access_token("u1", "alice", "viewer", org_id="org9")
    assert _decode(token)["org_id"] == "org9"


def test_token_omits_org_id_when_absent():
    token = auth_core.create_access_token("u1", "alice", "viewer")
    assert "org_id" not in _decode(token)


async def test_resolve_user_surfaces_org_id():
    token = auth_core.create_access_token("u1", "alice", "viewer", org_id="org9")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await auth_core.resolve_user(creds)
    assert user["org_id"] == "org9"


async def test_resolve_user_org_id_none_for_legacy_token():
    token = auth_core.create_access_token("u1", "alice", "viewer")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await auth_core.resolve_user(creds)
    assert user["org_id"] is None


# --- integration tests (Mongo) ---


@pytest.fixture()
async def db(monkeypatch):
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_indexes(database)
    await ensure_org_indexes(database)

    async def _get_db():
        return database

    async def _noop_log(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_routes, "get_db", _get_db)
    monkeypatch.setattr(auth_routes, "log_event", _noop_log)

    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


async def test_signup_creates_user_org_and_owner_membership(db, monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "signup_enabled", True)
    resp = await auth_routes.signup(
        SignupRequest(username="alice", password="password123", organization_name="Acme")
    )
    assert resp.organization.name == "Acme"
    assert resp.organization.role == OrgRole.OWNER
    assert _decode(resp.access_token)["org_id"] == resp.organization.id

    membership = await get_membership(db, resp.organization.id, resp.user.id)
    assert membership is not None
    assert membership["role"] == OrgRole.OWNER


async def test_signup_disabled_returns_403(db, monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "signup_enabled", False)
    with pytest.raises(HTTPException) as exc:
        await auth_routes.signup(
            SignupRequest(username="bob", password="password123", organization_name="B")
        )
    assert exc.value.status_code == 403


async def test_signup_duplicate_username_returns_409(db, monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "signup_enabled", True)
    await auth_routes.signup(
        SignupRequest(username="carol", password="password123", organization_name="C")
    )
    with pytest.raises(HTTPException) as exc:
        await auth_routes.signup(
            SignupRequest(username="carol", password="password123", organization_name="C2")
        )
    assert exc.value.status_code == 409


async def test_login_attaches_org_context(db, monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "signup_enabled", True)
    su = await auth_routes.signup(
        SignupRequest(username="dave", password="password123", organization_name="D")
    )
    login_resp = await auth_routes.login(LoginRequest(username="dave", password="password123"))
    assert _decode(login_resp.access_token)["org_id"] == su.organization.id
