import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from docingest.config import settings
from docingest.db.mongodb import get_api_key, get_db
from docingest.models.user import UserRole
from docingest.services.rate_limiter import RateLimitResult, check_rate_limit

_api_key_header = APIKeyHeader(name="X-API-Key")
_bearer_scheme = HTTPBearer(auto_error=False)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# --- Password hashing ---


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# --- JWT ---


def create_access_token(user_id: str, username: str, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# --- JWT user dependencies ---


async def resolve_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> dict:
    """Validate JWT Bearer token and return user dict."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "user_id": payload["sub"],
        "username": payload["username"],
        "role": payload["role"],
    }


async def require_admin(user: dict = Depends(resolve_user)) -> dict:
    """Wrap resolve_user, checks role=admin."""
    if user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


CurrentUser = Annotated[dict, Depends(resolve_user)]
AdminUser = Annotated[dict, Depends(require_admin)]


# --- API key tenant dependencies (unchanged) ---


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
