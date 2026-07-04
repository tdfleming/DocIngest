"""API key management service.

Extracted from scripts/create_api_key.py for use by the admin API.
"""

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from docingest.config import settings


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (plaintext, key_hash)."""
    plaintext = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, key_hash


async def create_api_key(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    tenant_name: str,
    rate_limit: int | None = None,
    org_id: str | None = None,
    scopes: list[str] | None = None,
) -> tuple[str, dict]:
    """Create a new API key. Returns (plaintext, doc).

    ``org_id`` links the key to an organization (typically equal to tenant_id).
    ``scopes`` restricts the key; None means full access.
    """
    plaintext, key_hash = generate_api_key()
    doc = {
        "key_hash": key_hash,
        "key_prefix": plaintext[:8],
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "org_id": org_id,
        "scopes": [str(s) for s in scopes] if scopes else None,
        "rate_limit": rate_limit or settings.default_rate_limit,
        "enabled": True,
        "created_at": datetime.now(UTC),
    }
    result = await db.api_keys.insert_one(doc)
    doc["_id"] = result.inserted_id
    return plaintext, doc


async def list_api_keys(db: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    """List all API keys, excluding the key_hash."""
    cursor = db.api_keys.find(
        {},
        {"key_hash": 0},
    ).sort("created_at", -1)
    return await cursor.to_list(length=1000)


async def update_api_key(
    db: AsyncIOMotorDatabase,
    key_id: str,
    updates: dict[str, Any],
) -> bool:
    """Update an API key's metadata. Returns True if found."""
    result = await db.api_keys.update_one(
        {"_id": ObjectId(key_id)},
        {"$set": updates},
    )
    return result.matched_count > 0


async def delete_api_key(db: AsyncIOMotorDatabase, key_id: str) -> bool:
    """Delete an API key. Returns True if found."""
    result = await db.api_keys.delete_one({"_id": ObjectId(key_id)})
    return result.deleted_count > 0
