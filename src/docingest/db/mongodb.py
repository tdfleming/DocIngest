from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from docingest.config import settings
from docingest.models.document import DocumentStatus

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        _db = _client[settings.mongodb_database]
    return _db


async def close_db() -> None:
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.documents.create_index([("tenant_id", 1), ("source_hash", 1)])
    await db.documents.create_index([("tenant_id", 1), ("status", 1)])
    await db.documents.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.api_keys.create_index("key_hash", unique=True)
    await db.api_keys.create_index("tenant_id")
    await db.users.create_index("username", unique=True)
    await db.app_logs.create_index("created_at", expireAfterSeconds=604800)  # 7-day TTL
    await db.app_logs.create_index([("level", 1), ("created_at", -1)])
    await db.app_logs.create_index("trace_id")
    await db.app_logs.create_index("doc_id")
    await db.app_logs.create_index("component")


# --- Document operations ---


async def insert_document(db: AsyncIOMotorDatabase, doc: dict[str, Any]) -> str:
    doc["created_at"] = datetime.now(UTC)
    doc["updated_at"] = datetime.now(UTC)
    result = await db.documents.insert_one(doc)
    return str(result.inserted_id)


async def get_document(db: AsyncIOMotorDatabase, doc_id: str, tenant_id: str) -> dict | None:
    return await db.documents.find_one({"_id": ObjectId(doc_id), "tenant_id": tenant_id})


async def find_by_hash(db: AsyncIOMotorDatabase, tenant_id: str, source_hash: str) -> dict | None:
    return await db.documents.find_one({"tenant_id": tenant_id, "source_hash": source_hash})


async def update_document_status(
    db: AsyncIOMotorDatabase,
    doc_id: str,
    status: DocumentStatus,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    update: dict[str, Any] = {"$set": {"status": status, "updated_at": datetime.now(UTC)}}
    if extra_fields:
        update["$set"].update(extra_fields)
    await db.documents.update_one({"_id": ObjectId(doc_id)}, update)


async def list_documents(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    status: str | None = None,
    content_type: str | None = None,
    page: int = 1,
    per_page: int = 50,
    sort_field: str = "created_at",
    sort_order: int = -1,
) -> tuple[list[dict], int]:
    query: dict[str, Any] = {"tenant_id": tenant_id}
    if status:
        query["status"] = status
    if content_type:
        query["content_type"] = content_type

    total = await db.documents.count_documents(query)
    cursor = (
        db.documents.find(query)
        .sort(sort_field, sort_order)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    docs = await cursor.to_list(length=per_page)
    return docs, total


async def delete_document(db: AsyncIOMotorDatabase, doc_id: str, tenant_id: str) -> bool:
    result = await db.documents.delete_one({"_id": ObjectId(doc_id), "tenant_id": tenant_id})
    return result.deleted_count > 0


async def increment_version(db: AsyncIOMotorDatabase, doc_id: str) -> None:
    await db.documents.update_one(
        {"_id": ObjectId(doc_id)},
        {"$inc": {"version": 1}, "$set": {"status": "pending", "updated_at": datetime.now(UTC)}},
    )


# --- API key operations ---


async def get_api_key(db: AsyncIOMotorDatabase, key_hash: str) -> dict | None:
    return await db.api_keys.find_one({"key_hash": key_hash, "enabled": True})
