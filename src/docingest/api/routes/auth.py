"""Auth routes: login, bootstrap, user management."""

import asyncio
from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from docingest.api.auth import (
    AdminUser,
    CurrentUser,
    create_access_token,
    hash_password,
    verify_password,
)
from docingest.config import settings
from docingest.db.mongodb import get_db
from docingest.db.organizations import create_organization, list_user_organizations
from docingest.models.organization import OrganizationResponse, OrgRole
from docingest.models.user import (
    CreateUserRequest,
    LoginRequest,
    LoginResponse,
    SignupRequest,
    UpdateUserRequest,
    UserResponse,
    UserRole,
)
from docingest.services.app_logger import log_event

router = APIRouter(prefix="/auth")


class SignupResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    organization: OrganizationResponse


def _user_response(doc: dict) -> UserResponse:
    return UserResponse(
        id=str(doc["_id"]),
        username=doc["username"],
        role=doc["role"],
        created_at=doc["created_at"].isoformat(),
    )


@router.get("/status")
async def auth_status():
    """Returns whether any users exist (no auth required, for bootstrap detection)."""
    db = await get_db()
    count = await db.users.count_documents({})
    return {"has_users": count > 0}


@router.post("/bootstrap")
async def bootstrap(body: CreateUserRequest):
    """Create first admin user. Only works when 0 users exist."""
    db = await get_db()
    count = await db.users.count_documents({})
    if count > 0:
        raise HTTPException(status_code=400, detail="Users already exist. Use login instead.")

    user_doc = {
        "username": body.username,
        "password_hash": hash_password(body.password),
        "role": UserRole.ADMIN,
        "created_at": datetime.now(UTC),
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    token = create_access_token(user_id, body.username, UserRole.ADMIN)

    asyncio.create_task(
        log_event("info", "bootstrap_admin_created", "auth", user_id=user_id)
    )

    user_doc["_id"] = result.inserted_id
    return LoginResponse(
        access_token=token,
        user=_user_response(user_doc),
    )


@router.post("/signup", status_code=201)
async def signup(body: SignupRequest):
    """Self-serve signup: create a user and their first organization.

    Disabled unless SIGNUP_ENABLED=true. The new user is the OWNER of the org;
    the returned JWT carries the org context.
    """
    if not settings.signup_enabled:
        raise HTTPException(status_code=403, detail="Self-serve signup is disabled")

    db = await get_db()
    if await db.users.find_one({"username": body.username}):
        raise HTTPException(status_code=409, detail="Username already exists")

    user_doc = {
        "username": body.username,
        "password_hash": hash_password(body.password),
        "role": UserRole.VIEWER,
        "created_at": datetime.now(UTC),
    }
    try:
        result = await db.users.insert_one(user_doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Username already exists") from None
    user_id = str(result.inserted_id)
    user_doc["_id"] = result.inserted_id

    org = await create_organization(db, body.organization_name, owner_user_id=user_id)
    org_id = str(org["_id"])
    token = create_access_token(user_id, body.username, UserRole.VIEWER, org_id=org_id)

    asyncio.create_task(
        log_event("info", "signup", "auth", user_id=user_id, details={"org_id": org_id})
    )

    return SignupResponse(
        access_token=token,
        user=_user_response(user_doc),
        organization=OrganizationResponse(
            id=org_id,
            name=org["name"],
            slug=org["slug"],
            role=OrgRole.OWNER,
            created_at=org["created_at"].isoformat(),
        ),
    )


@router.post("/login")
async def login(body: LoginRequest):
    """Validate credentials, return JWT (with the user's default org, if any)."""
    db = await get_db()
    user = await db.users.find_one({"username": body.username})
    if not user or not verify_password(body.password, user["password_hash"]):
        asyncio.create_task(
            log_event(
                "warning",
                "login_failed",
                "auth",
                details={"username": body.username},
            )
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = str(user["_id"])
    orgs = await list_user_organizations(db, user_id)
    org_id = str(orgs[0]["_id"]) if orgs else None
    token = create_access_token(user_id, user["username"], user["role"], org_id=org_id)

    asyncio.create_task(
        log_event("info", "login_success", "auth", user_id=user_id)
    )

    return LoginResponse(
        access_token=token,
        user=_user_response(user),
    )


@router.get("/me")
async def me(user: CurrentUser):
    """Return current user info."""
    db = await get_db()
    doc = await db.users.find_one({"_id": ObjectId(user["user_id"])})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_response(doc)


@router.get("/users")
async def list_users(user: AdminUser):
    """List all users (admin only)."""
    db = await get_db()
    cursor = db.users.find({}, {"password_hash": 0}).sort("created_at", -1)
    users = await cursor.to_list(length=1000)
    return [_user_response(u) for u in users]


@router.post("/users", status_code=201)
async def create_user(body: CreateUserRequest, user: AdminUser):
    """Create a new user (admin only)."""
    db = await get_db()

    existing = await db.users.find_one({"username": body.username})
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user_doc = {
        "username": body.username,
        "password_hash": hash_password(body.password),
        "role": body.role,
        "created_at": datetime.now(UTC),
    }
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    asyncio.create_task(
        log_event(
            "info",
            "user_created",
            "auth",
            user_id=user["user_id"],
            details={"new_username": body.username, "role": body.role},
        )
    )

    return _user_response(user_doc)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UpdateUserRequest, user: AdminUser):
    """Update a user (admin only)."""
    db = await get_db()

    updates: dict = {}
    if body.password is not None:
        updates["password_hash"] = hash_password(body.password)
    if body.role is not None:
        updates["role"] = body.role

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    asyncio.create_task(
        log_event(
            "info",
            "user_updated",
            "auth",
            user_id=user["user_id"],
            details={"target_user_id": user_id},
        )
    )

    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    return _user_response(doc)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: AdminUser):
    """Delete a user (admin only). Cannot delete yourself."""
    if user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    db = await get_db()
    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    asyncio.create_task(
        log_event(
            "info",
            "user_deleted",
            "auth",
            user_id=user["user_id"],
            details={"deleted_user_id": user_id},
        )
    )

    return {"id": user_id, "status": "deleted"}
