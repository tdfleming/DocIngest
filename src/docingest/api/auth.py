import hashlib
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from docingest.db.mongodb import get_api_key, get_db
from docingest.services.rate_limiter import RateLimitResult, check_rate_limit

_api_key_header = APIKeyHeader(name="X-API-Key")


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def resolve_tenant(api_key: str = Security(_api_key_header)) -> dict:
    """Resolve tenant from API key without rate limiting (for workers)."""
    db = await get_db()
    key_doc = await get_api_key(db, hash_api_key(api_key))
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {
        "tenant_id": key_doc["tenant_id"],
        "tenant_name": key_doc.get("tenant_name", ""),
        "rate_limit": key_doc.get("rate_limit", 100),
    }


async def resolve_tenant_with_rate_limit(
    request: Request,
    api_key: str = Security(_api_key_header),
) -> dict:
    """Resolve tenant and enforce per-key rate limiting."""
    db = await get_db()
    key_hash = hash_api_key(api_key)
    key_doc = await get_api_key(db, key_hash)
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid API key")

    tenant = {
        "tenant_id": key_doc["tenant_id"],
        "tenant_name": key_doc.get("tenant_name", ""),
        "rate_limit": key_doc.get("rate_limit", 100),
    }

    result: RateLimitResult = await check_rate_limit(key_hash, tenant["rate_limit"])

    # Store for middleware to add response headers
    request.state.rate_limit = result

    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(result.reset)},
        )

    return tenant


Tenant = Annotated[dict, Depends(resolve_tenant_with_rate_limit)]
