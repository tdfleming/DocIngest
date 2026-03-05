"""Admin routes: log viewer + API key management."""

from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from docingest.api.auth import AdminUser
from docingest.db.mongodb import get_db
from docingest.services.api_key_service import (
    create_api_key,
    delete_api_key,
    list_api_keys,
    update_api_key,
)

router = APIRouter(prefix="/admin")


# --- Log viewer ---


@router.get("/logs")
async def get_logs(
    user: AdminUser,
    level: str | None = Query(None),
    component: str | None = Query(None),
    trace_id: str | None = Query(None),
    doc_id: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Query application logs with filters (admin only)."""
    db = await get_db()
    query: dict = {}

    if level:
        query["level"] = level
    if component:
        query["component"] = component
    if trace_id:
        query["trace_id"] = trace_id
    if doc_id:
        query["doc_id"] = doc_id
    if start_time or end_time:
        time_filter: dict = {}
        if start_time:
            time_filter["$gte"] = datetime.fromisoformat(start_time)
        if end_time:
            time_filter["$lte"] = datetime.fromisoformat(end_time)
        query["created_at"] = time_filter

    total = await db.app_logs.count_documents(query)
    cursor = (
        db.app_logs.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    logs = await cursor.to_list(length=per_page)

    for log_entry in logs:
        log_entry["id"] = str(log_entry.pop("_id"))
        log_entry["created_at"] = log_entry["created_at"].isoformat()

    return {"logs": logs, "total": total, "page": page, "per_page": per_page}


# --- API key management ---


class CreateApiKeyRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    tenant_name: str = Field(min_length=1)
    rate_limit: int = Field(100, ge=1)


class UpdateApiKeyRequest(BaseModel):
    tenant_name: str | None = None
    rate_limit: int | None = Field(None, ge=1)
    enabled: bool | None = None


@router.get("/api-keys")
async def get_api_keys(user: AdminUser):
    """List all API keys with metadata (admin only)."""
    db = await get_db()
    keys = await list_api_keys(db)
    for key in keys:
        key["id"] = str(key.pop("_id"))
        if "created_at" in key and hasattr(key["created_at"], "isoformat"):
            key["created_at"] = key["created_at"].isoformat()
    return keys


@router.post("/api-keys", status_code=201)
async def create_api_key_route(body: CreateApiKeyRequest, user: AdminUser):
    """Create a new API key (admin only). Returns plaintext once."""
    db = await get_db()
    plaintext, doc = await create_api_key(
        db, body.tenant_id, body.tenant_name, body.rate_limit
    )
    return {
        "id": str(doc["_id"]),
        "api_key": plaintext,
        "key_prefix": doc["key_prefix"],
        "tenant_id": doc["tenant_id"],
        "tenant_name": doc["tenant_name"],
        "rate_limit": doc["rate_limit"],
        "enabled": doc["enabled"],
        "created_at": doc["created_at"].isoformat(),
    }


@router.patch("/api-keys/{key_id}")
async def update_api_key_route(
    key_id: str, body: UpdateApiKeyRequest, user: AdminUser
):
    """Update an API key (admin only)."""
    updates: dict = {}
    if body.tenant_name is not None:
        updates["tenant_name"] = body.tenant_name
    if body.rate_limit is not None:
        updates["rate_limit"] = body.rate_limit
    if body.enabled is not None:
        updates["enabled"] = body.enabled

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    db = await get_db()
    if not await update_api_key(db, key_id, updates):
        raise HTTPException(status_code=404, detail="API key not found")

    # Fetch updated doc
    doc = await db.api_keys.find_one({"_id": ObjectId(key_id)}, {"key_hash": 0})
    doc["id"] = str(doc.pop("_id"))
    if hasattr(doc.get("created_at"), "isoformat"):
        doc["created_at"] = doc["created_at"].isoformat()
    return doc


@router.delete("/api-keys/{key_id}")
async def delete_api_key_route(key_id: str, user: AdminUser):
    """Delete an API key (admin only)."""
    db = await get_db()
    if not await delete_api_key(db, key_id):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"id": key_id, "status": "deleted"}
