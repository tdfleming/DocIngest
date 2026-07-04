"""Tests for API key scopes and org linkage.

Scope logic and the require_scope dependency are pure (no Mongo). Key creation
storage is an integration test requiring MongoDB at localhost:27017.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.api.auth import _key_to_tenant, require_scope
from docingest.models.api_key import ApiKeyScope, key_has_scope
from docingest.services.api_key_service import create_api_key

TEST_DB_NAME = "docingest_test_api_key_scopes"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")


# --- pure unit tests ---


def test_legacy_key_has_full_access():
    assert key_has_scope(None, ApiKeyScope.READ) is True
    assert key_has_scope([], ApiKeyScope.INGEST) is True


def test_admin_scope_is_superset():
    assert key_has_scope(["admin"], ApiKeyScope.READ) is True
    assert key_has_scope(["admin"], ApiKeyScope.INGEST) is True


def test_specific_scopes_enforced():
    assert key_has_scope(["read"], ApiKeyScope.READ) is True
    assert key_has_scope(["read"], ApiKeyScope.INGEST) is False
    assert key_has_scope(["ingest"], ApiKeyScope.INGEST) is True
    assert key_has_scope(["ingest"], ApiKeyScope.READ) is False


def test_key_to_tenant_surfaces_org_and_scopes():
    tenant = _key_to_tenant({"tenant_id": "t1", "org_id": "o1", "scopes": ["read"]})
    assert tenant["tenant_id"] == "t1"
    assert tenant["org_id"] == "o1"
    assert tenant["scopes"] == ["read"]


def test_key_to_tenant_legacy_defaults():
    tenant = _key_to_tenant({"tenant_id": "t1"})
    assert tenant["org_id"] is None
    assert tenant["scopes"] is None


async def test_require_scope_allows_when_present():
    dep = require_scope(ApiKeyScope.INGEST)
    result = await dep({"tenant_id": "t", "scopes": ["ingest"]})
    assert result["tenant_id"] == "t"


async def test_require_scope_allows_legacy_key():
    dep = require_scope(ApiKeyScope.INGEST)
    result = await dep({"tenant_id": "t", "scopes": None})
    assert result["tenant_id"] == "t"


async def test_require_scope_denies_when_missing():
    dep = require_scope(ApiKeyScope.INGEST)
    with pytest.raises(HTTPException) as exc:
        await dep({"tenant_id": "t", "scopes": ["read"]})
    assert exc.value.status_code == 403


# --- integration test (Mongo) ---


@pytest.fixture()
async def db():
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


async def test_create_api_key_stores_org_and_scopes(db):
    plaintext, doc = await create_api_key(
        db, "org1", "Acme", org_id="org1", scopes=["read", "ingest"]
    )
    assert plaintext
    assert doc["org_id"] == "org1"
    assert doc["scopes"] == ["read", "ingest"]

    # Legacy-style creation leaves scopes/org unset (full access).
    _, legacy = await create_api_key(db, "tenant-x", "X")
    assert legacy["org_id"] is None
    assert legacy["scopes"] is None
