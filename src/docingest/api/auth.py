import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from docingest.config import settings
from docingest.db.mongodb import get_api_key, get_db
from docingest.db.organizations import get_membership
from docingest.models.api_key import ApiKeyScope, key_has_scope
from docingest.models.organization import OrgRole
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


def create_access_token(
    user_id: str, username: str, role: str, org_id: str | None = None
) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire,
    }
    if org_id:
        payload["org_id"] = org_id
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# --- JWT user dependencies ---


async def resolve_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),  # noqa: B008
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
        raise HTTPException(status_code=401, detail="Token expired") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    return {
        "user_id": payload["sub"],
        "username": payload["username"],
        "role": payload["role"],
        "org_id": payload.get("org_id"),
    }


async def require_admin(user: dict = Depends(resolve_user)) -> dict:  # noqa: B008
    """Wrap resolve_user, checks role=admin."""
    if user["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


CurrentUser = Annotated[dict, Depends(resolve_user)]
AdminUser = Annotated[dict, Depends(require_admin)]


# --- Organization context (JWT) ---


async def resolve_org(user: dict = Depends(resolve_user)) -> dict:  # noqa: B008
    """Resolve the active organization from the JWT and confirm membership."""
    org_id = user.get("org_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="No active organization in token")
    db = await get_db()
    membership = await get_membership(db, org_id, user["user_id"])
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return {"org_id": org_id, "user_id": user["user_id"], "role": membership["role"]}


def require_org_role(*allowed: OrgRole):
    """Dependency factory: require the current org membership to hold a role."""

    async def _dep(org: dict = Depends(resolve_org)) -> dict:  # noqa: B008
        if org["role"] not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient organization role")
        return org

    return _dep


CurrentOrg = Annotated[dict, Depends(resolve_org)]
OrgManager = Annotated[dict, Depends(require_org_role(OrgRole.OWNER, OrgRole.ADMIN))]


# --- API key tenant dependencies ---


def _key_to_tenant(key_doc: dict) -> dict:
    """Project an api_keys document into the tenant context passed to routes."""
    return {
        "tenant_id": key_doc["tenant_id"],
        "tenant_name": key_doc.get("tenant_name", ""),
        "rate_limit": key_doc.get("rate_limit", 100),
        "org_id": key_doc.get("org_id"),
        "scopes": key_doc.get("scopes"),
    }


async def resolve_tenant(api_key: str = Security(_api_key_header)) -> dict:
    """Resolve tenant from API key without rate limiting (for workers)."""
    db = await get_db()
    key_doc = await get_api_key(db, hash_api_key(api_key))
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return _key_to_tenant(key_doc)


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

    tenant = _key_to_tenant(key_doc)

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


# --- API key scope enforcement ---


def require_scope(scope: ApiKeyScope):
    """Dependency factory: require the resolved API key to hold ``scope``.

    Legacy keys (no scopes) and admin-scoped keys pass every check.
    """

    async def _dep(tenant: Tenant) -> dict:
        if not key_has_scope(tenant.get("scopes"), scope):
            raise HTTPException(
                status_code=403, detail=f"API key lacks required scope: {scope}"
            )
        return tenant

    return _dep


ReadScope = Annotated[dict, Depends(require_scope(ApiKeyScope.READ))]
IngestScope = Annotated[dict, Depends(require_scope(ApiKeyScope.INGEST))]
AdminScope = Annotated[dict, Depends(require_scope(ApiKeyScope.ADMIN))]
