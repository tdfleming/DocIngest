"""Graph store CRUD operations for entities, relationships, and communities.

All functions are async module-level functions taking db: AsyncIOMotorDatabase
as the first parameter, following the pattern established in mongodb.py.
"""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

import numpy as np
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_graph_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create compound indexes for graph collections."""
    # Entities: unique dedup index + lookup indexes
    await db.entities.create_index(
        [("tenant_id", 1), ("name", 1), ("entity_type", 1)],
        unique=True,
    )
    await db.entities.create_index([("tenant_id", 1), ("doc_ids", 1)])
    await db.entities.create_index([("tenant_id", 1), ("entity_type", 1)])

    # Relationships: unique dedup index + lookup indexes
    await db.relationships.create_index(
        [
            ("tenant_id", 1),
            ("source_entity_id", 1),
            ("target_entity_id", 1),
            ("relation_type", 1),
        ],
        unique=True,
    )
    await db.relationships.create_index([("tenant_id", 1), ("source_entity_id", 1)])
    await db.relationships.create_index([("tenant_id", 1), ("target_entity_id", 1)])
    await db.relationships.create_index([("tenant_id", 1), ("doc_ids", 1)])

    # Communities: lookup indexes
    await db.communities.create_index([("tenant_id", 1), ("level", 1)])
    await db.communities.create_index(
        [("tenant_id", 1), ("level", 1), ("title", 1)],
        unique=True,
    )
    await db.communities.create_index([("tenant_id", 1), ("entity_ids", 1)])


async def upsert_entity(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    name: str,
    entity_type: str,
    doc_id: str,
    chunk_ids: list[str],
    aliases: list[str] | None = None,
) -> str:
    """Upsert an entity, deduplicating by (tenant_id, name, entity_type).

    Merges doc_ids, chunk_ids, aliases via $addToSet and increments mention_count.
    Returns the entity ID as a string.
    """
    if aliases is None:
        aliases = []
    now = datetime.now(UTC)

    result = await db.entities.update_one(
        {
            "tenant_id": tenant_id,
            "name": name,
            "entity_type": entity_type,
        },
        {
            "$set": {"updated_at": now},
            "$addToSet": {
                "doc_ids": {"$each": [doc_id]},
                "chunk_ids": {"$each": chunk_ids},
                "aliases": {"$each": aliases},
            },
            "$inc": {"mention_count": 1},
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "name": name,
                "entity_type": entity_type,
                "embedding": None,
                "metadata": {},
                "created_at": now,
            },
        },
        upsert=True,
    )

    if result.upserted_id:
        return str(result.upserted_id)

    # Return existing doc id
    existing = await db.entities.find_one(
        {"tenant_id": tenant_id, "name": name, "entity_type": entity_type},
        {"_id": 1},
    )
    return str(existing["_id"]) if existing else ""


async def upsert_relationship(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    source_entity_id: str,
    target_entity_id: str,
    relation_type: str,
    description: str,
    doc_id: str,
    chunk_ids: list[str],
) -> str:
    """Upsert a relationship, deduplicating by (tenant_id, source, target, relation_type).

    Merges doc_ids and chunk_ids via $addToSet.
    Returns the relationship ID as a string.
    """
    now = datetime.now(UTC)

    result = await db.relationships.update_one(
        {
            "tenant_id": tenant_id,
            "source_entity_id": source_entity_id,
            "target_entity_id": target_entity_id,
            "relation_type": relation_type,
        },
        {
            "$set": {"updated_at": now, "description": description},
            "$addToSet": {
                "doc_ids": {"$each": [doc_id]},
                "chunk_ids": {"$each": chunk_ids},
            },
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "source_entity_id": source_entity_id,
                "target_entity_id": target_entity_id,
                "relation_type": relation_type,
                "weight": 1.0,
                "created_at": now,
            },
        },
        upsert=True,
    )

    if result.upserted_id:
        return str(result.upserted_id)

    existing = await db.relationships.find_one(
        {
            "tenant_id": tenant_id,
            "source_entity_id": source_entity_id,
            "target_entity_id": target_entity_id,
            "relation_type": relation_type,
        },
        {"_id": 1},
    )
    return str(existing["_id"]) if existing else ""


async def get_entity_by_id(
    db: AsyncIOMotorDatabase, entity_id: str, tenant_id: str | None = None
) -> dict[str, Any] | None:
    """Find a single entity by ObjectId. Returns dict or None.

    If tenant_id is provided, includes it in the query for tenant-scope enforcement.
    """
    selector: dict[str, Any] = {"_id": ObjectId(entity_id)}
    if tenant_id is not None:
        selector["tenant_id"] = tenant_id
    return await db.entities.find_one(selector)


async def find_entities_by_names(
    db: AsyncIOMotorDatabase, tenant_id: str, names: list[str]
) -> list[dict[str, Any]]:
    """Batch lookup entities by tenant and name list."""
    cursor = db.entities.find({"tenant_id": tenant_id, "name": {"$in": names}})
    return await cursor.to_list(length=None)


async def get_entity_neighbors(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    entity_id: str,
    max_hops: int = 1,
) -> list[dict[str, Any]]:
    """Get connected entities for an entity.

    For max_hops==1: two-step query (find relationships, fetch connected entities).
    For max_hops>1: uses $graphLookup for multi-hop traversal.
    """
    eid = str(ObjectId(entity_id))  # Normalize

    if max_hops == 1:
        return await _get_neighbors_one_hop(db, tenant_id, eid)
    return await _get_neighbors_multi_hop(db, tenant_id, eid, max_hops)


async def _get_neighbors_one_hop(
    db: AsyncIOMotorDatabase, tenant_id: str, entity_id: str
) -> list[dict[str, Any]]:
    """Two-step query for 1-hop neighbors."""
    # Step 1: Find relationships involving this entity
    rels = await db.relationships.find(
        {
            "tenant_id": tenant_id,
            "$or": [
                {"source_entity_id": entity_id},
                {"target_entity_id": entity_id},
            ],
        }
    ).to_list(length=500)

    # Step 2: Collect neighbor entity IDs
    neighbor_ids: set[str] = set()
    for r in rels:
        if r["source_entity_id"] != entity_id:
            neighbor_ids.add(r["source_entity_id"])
        if r["target_entity_id"] != entity_id:
            neighbor_ids.add(r["target_entity_id"])

    if not neighbor_ids:
        return []

    # Step 3: Fetch neighbor entities
    return await db.entities.find(
        {
            "_id": {"$in": [ObjectId(nid) for nid in neighbor_ids]},
            "tenant_id": tenant_id,
        }
    ).to_list(length=500)


async def _get_neighbors_multi_hop(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    entity_id: str,
    max_hops: int,
) -> list[dict[str, Any]]:
    """$graphLookup for multi-hop traversal."""
    pipeline = [
        {"$match": {"_id": ObjectId(entity_id), "tenant_id": tenant_id}},
        {
            "$graphLookup": {
                "from": "relationships",
                "startWith": {"$toString": "$_id"},
                "connectFromField": "target_entity_id",
                "connectToField": "source_entity_id",
                "as": "connections",
                "maxDepth": max_hops - 1,
                "depthField": "hop",
                "restrictSearchWithMatch": {"tenant_id": tenant_id},
            }
        },
    ]
    result = await db.entities.aggregate(pipeline).to_list(length=1)
    if not result or not result[0].get("connections"):
        return []

    # Extract connected entity IDs from relationships
    connected_ids: set[str] = set()
    for conn in result[0]["connections"]:
        connected_ids.add(conn.get("source_entity_id", ""))
        connected_ids.add(conn.get("target_entity_id", ""))
    connected_ids.discard(entity_id)
    connected_ids.discard("")

    if not connected_ids:
        return []

    return await db.entities.find(
        {
            "_id": {"$in": [ObjectId(nid) for nid in connected_ids]},
            "tenant_id": tenant_id,
        }
    ).to_list(length=500)


async def list_entities(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    entity_type: str | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """Paginated entity listing. Returns (docs, total_count) tuple.

    Optional entity_type and q (name substring, case-insensitive) filters are AND-combined.
    """
    query: dict[str, Any] = {"tenant_id": tenant_id}
    if entity_type:
        query["entity_type"] = entity_type
    if q:
        query["name"] = {"$regex": re.escape(q), "$options": "i"}

    total = await db.entities.count_documents(query)
    cursor = (
        db.entities.find(query)
        .sort("name", 1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    docs = await cursor.to_list(length=per_page)
    return docs, total


async def upsert_community(
    db: AsyncIOMotorDatabase, tenant_id: str, community_data: dict[str, Any]
) -> str:
    """Upsert a community by (tenant_id, level, title)."""
    now = datetime.now(UTC)
    level = community_data["level"]
    title = community_data.get("title", "")

    set_fields: dict[str, Any] = {
        "updated_at": now,
        "summary": community_data.get("summary", ""),
        "entity_ids": community_data.get("entity_ids", []),
    }
    if "summary_embedding" in community_data:
        set_fields["summary_embedding"] = community_data["summary_embedding"]
    if "parent_community_id" in community_data:
        set_fields["parent_community_id"] = community_data["parent_community_id"]
    if "child_community_ids" in community_data:
        set_fields["child_community_ids"] = community_data["child_community_ids"]

    result = await db.communities.update_one(
        {"tenant_id": tenant_id, "level": level, "title": title},
        {
            "$set": set_fields,
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "level": level,
                "title": title,
                "created_at": now,
            },
        },
        upsert=True,
    )

    if result.upserted_id:
        return str(result.upserted_id)

    existing = await db.communities.find_one(
        {"tenant_id": tenant_id, "level": level, "title": title},
        {"_id": 1},
    )
    return str(existing["_id"]) if existing else ""


async def get_communities_by_level(
    db: AsyncIOMotorDatabase, tenant_id: str, level: int
) -> list[dict[str, Any]]:
    """Get all communities at a specific level for a tenant."""
    return await db.communities.find(
        {"tenant_id": tenant_id, "level": level}
    ).to_list(length=None)


async def list_communities(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    level: int | None = None,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """Paginated community listing with optional level filter. Returns (docs, total)."""
    query: dict[str, Any] = {"tenant_id": tenant_id}
    if level is not None:
        query["level"] = level
    total = await db.communities.count_documents(query)
    cursor = (
        db.communities.find(query)
        .sort([("level", 1), ("title", 1)])
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    docs = await cursor.to_list(length=per_page)
    return docs, total


async def get_community_by_id(
    db: AsyncIOMotorDatabase, community_id: str, tenant_id: str
) -> dict[str, Any] | None:
    """Find a single community by ObjectId with tenant scope enforcement."""
    return await db.communities.find_one(
        {"_id": ObjectId(community_id), "tenant_id": tenant_id}
    )


async def search_communities_by_embedding(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    query_embedding: list[float],
    limit: int = 5,
) -> list[tuple[float, dict[str, Any]]]:
    """Search communities by cosine similarity using Python-side numpy computation.

    Fetches all communities with summary_embedding for the tenant and ranks them.
    Suitable for small community counts (< 1000 per tenant).
    Returns list of (score, community_dict) tuples sorted by score descending.
    """
    communities = await db.communities.find(
        {"tenant_id": tenant_id, "summary_embedding": {"$exists": True, "$ne": None}},
    ).to_list(length=None)

    if not communities:
        return []

    query_vec = np.array(query_embedding)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return [(0.0, comm) for comm in communities[:limit]]

    scored: list[tuple[float, dict[str, Any]]] = []
    for comm in communities:
        emb = np.array(comm["summary_embedding"])
        emb_norm = np.linalg.norm(emb)
        if emb_norm == 0:
            similarity = 0.0
        else:
            similarity = float(np.dot(query_vec, emb) / (query_norm * emb_norm))
        scored.append((similarity, comm))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


async def delete_doc_graph_data(
    db: AsyncIOMotorDatabase, tenant_id: str, doc_id: str
) -> None:
    """Remove doc references from entities and relationships, delete orphans.

    1. $pull doc_id from doc_ids arrays, $inc mention_count by -1 on entities
    2. Delete entities/relationships where doc_ids becomes empty
    """
    # Step 1: Pull doc references and decrement mention count
    await asyncio.gather(
        db.entities.update_many(
            {"tenant_id": tenant_id, "doc_ids": doc_id},
            {
                "$pull": {"doc_ids": doc_id},
                "$inc": {"mention_count": -1},
            },
        ),
        db.relationships.update_many(
            {"tenant_id": tenant_id, "doc_ids": doc_id},
            {"$pull": {"doc_ids": doc_id}},
        ),
    )

    # Step 2: Remove orphaned entities/relationships (empty doc_ids)
    await asyncio.gather(
        db.entities.delete_many({"tenant_id": tenant_id, "doc_ids": {"$size": 0}}),
        db.relationships.delete_many(
            {"tenant_id": tenant_id, "doc_ids": {"$size": 0}}
        ),
    )


async def get_graph_stats(
    db: AsyncIOMotorDatabase, tenant_id: str
) -> dict[str, int]:
    """Count documents per graph collection for a tenant."""
    query = {"tenant_id": tenant_id}
    entity_count, relationship_count, community_count = await asyncio.gather(
        db.entities.count_documents(query),
        db.relationships.count_documents(query),
        db.communities.count_documents(query),
    )
    return {
        "entity_count": entity_count,
        "relationship_count": relationship_count,
        "community_count": community_count,
    }
