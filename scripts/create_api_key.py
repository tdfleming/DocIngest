"""Utility script to create API keys for tenants.

Usage:
    python scripts/create_api_key.py <tenant_id> <tenant_name>

Prints the generated API key (only shown once — store it securely).
"""

import asyncio
import hashlib
import secrets
import sys

from motor.motor_asyncio import AsyncIOMotorClient

from docingest.config import settings


async def create_key(tenant_id: str, tenant_name: str) -> str:
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    api_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    await db.api_keys.insert_one({
        "key_hash": key_hash,
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "rate_limit": settings.default_rate_limit,
        "enabled": True,
    })

    client.close()
    return api_key


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_api_key.py <tenant_id> <tenant_name>")
        sys.exit(1)

    tenant_id = sys.argv[1]
    tenant_name = sys.argv[2]

    key = asyncio.run(create_key(tenant_id, tenant_name))
    print(f"Tenant:  {tenant_name} ({tenant_id})")
    print(f"API Key: {key}")
    print("Store this key securely — it cannot be retrieved later.")


if __name__ == "__main__":
    main()
