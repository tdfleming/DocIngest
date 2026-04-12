"""Integration tests for graph_store.py CRUD operations.

Requires MongoDB running at localhost:27017 (or MONGODB_URI env var).
"""

import asyncio
import os

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.db.graph_store import (
    delete_doc_graph_data,
    ensure_graph_indexes,
    find_entities_by_names,
    get_communities_by_level,
    get_entity_by_id,
    get_entity_neighbors,
    get_graph_stats,
    list_entities,
    search_communities_by_embedding,
    upsert_community,
    upsert_entity,
    upsert_relationship,
)

TEST_DB_NAME = "docingest_test_graph"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
TENANT = "test-tenant"


@pytest.fixture()
async def db():
    """Provide a clean test database for each test."""
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_graph_indexes(database)
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


# --- upsert_entity ---


async def test_upsert_entity_creates_new(db):
    eid = await upsert_entity(
        db, TENANT, "Acme Corp", "organization", "doc1", ["chunk1", "chunk2"]
    )
    assert isinstance(eid, str)
    assert len(eid) > 0

    entity = await get_entity_by_id(db, eid)
    assert entity is not None
    assert entity["name"] == "Acme Corp"
    assert entity["entity_type"] == "organization"
    assert entity["tenant_id"] == TENANT
    assert "doc1" in entity["doc_ids"]
    assert "chunk1" in entity["chunk_ids"]
    assert entity["mention_count"] == 1


async def test_upsert_entity_dedup_merges(db):
    eid1 = await upsert_entity(
        db, TENANT, "Acme Corp", "organization", "doc1", ["chunk1"]
    )
    eid2 = await upsert_entity(
        db, TENANT, "Acme Corp", "organization", "doc2", ["chunk2"], aliases=["ACME"]
    )
    assert eid1 == eid2

    entity = await get_entity_by_id(db, eid1)
    assert set(entity["doc_ids"]) == {"doc1", "doc2"}
    assert set(entity["chunk_ids"]) == {"chunk1", "chunk2"}
    assert "ACME" in entity["aliases"]
    assert entity["mention_count"] == 2


# --- upsert_relationship ---


async def test_upsert_relationship_creates_new(db):
    eid1 = await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    eid2 = await upsert_entity(db, TENANT, "Acme", "organization", "doc1", ["c1"])

    rid = await upsert_relationship(
        db, TENANT, eid1, eid2, "works_at", "Alice works at Acme", "doc1", ["c1"]
    )
    assert isinstance(rid, str)
    assert len(rid) > 0


async def test_upsert_relationship_dedup_merges(db):
    eid1 = await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    eid2 = await upsert_entity(db, TENANT, "Acme", "organization", "doc1", ["c1"])

    rid1 = await upsert_relationship(
        db, TENANT, eid1, eid2, "works_at", "Alice works at Acme", "doc1", ["c1"]
    )
    rid2 = await upsert_relationship(
        db, TENANT, eid1, eid2, "works_at", "Updated desc", "doc2", ["c2"]
    )
    assert rid1 == rid2

    rel = await db.relationships.find_one({"_id": __import__("bson").ObjectId(rid1)})
    assert set(rel["doc_ids"]) == {"doc1", "doc2"}
    assert set(rel["chunk_ids"]) == {"c1", "c2"}


# --- get_entity_by_id ---


async def test_get_entity_by_id_returns_none_for_missing(db):
    from bson import ObjectId

    result = await get_entity_by_id(db, str(ObjectId()))
    assert result is None


# --- find_entities_by_names ---


async def test_find_entities_by_names_returns_matches(db):
    await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    await upsert_entity(db, TENANT, "Bob", "person", "doc1", ["c1"])
    await upsert_entity(db, TENANT, "Acme", "organization", "doc1", ["c1"])

    results = await find_entities_by_names(db, TENANT, ["Alice", "Acme"])
    names = {e["name"] for e in results}
    assert names == {"Alice", "Acme"}


async def test_find_entities_by_names_empty_for_no_match(db):
    results = await find_entities_by_names(db, TENANT, ["NonExistent"])
    assert results == []


# --- list_entities ---


async def test_list_entities_returns_paginated(db):
    for i in range(5):
        await upsert_entity(db, TENANT, f"Entity{i}", "person", "doc1", ["c1"])

    docs, total = await list_entities(db, TENANT, page=1, per_page=3)
    assert total == 5
    assert len(docs) == 3

    docs2, total2 = await list_entities(db, TENANT, page=2, per_page=3)
    assert total2 == 5
    assert len(docs2) == 2


async def test_list_entities_filters_by_type(db):
    await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    await upsert_entity(db, TENANT, "Acme", "organization", "doc1", ["c1"])

    docs, total = await list_entities(db, TENANT, entity_type="person")
    assert total == 1
    assert docs[0]["name"] == "Alice"


# --- upsert_community / get_communities_by_level ---


async def test_upsert_community_and_get_by_level(db):
    await upsert_community(db, TENANT, {
        "level": 0,
        "title": "Tech Companies",
        "summary": "A community of tech companies",
        "entity_ids": ["e1", "e2"],
    })
    await upsert_community(db, TENANT, {
        "level": 1,
        "title": "Top Level",
        "summary": "Top-level community",
        "entity_ids": ["e1"],
    })

    level_0 = await get_communities_by_level(db, TENANT, 0)
    assert len(level_0) == 1
    assert level_0[0]["title"] == "Tech Companies"

    level_1 = await get_communities_by_level(db, TENANT, 1)
    assert len(level_1) == 1


# --- get_graph_stats ---


async def test_get_graph_stats(db):
    await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    await upsert_entity(db, TENANT, "Bob", "person", "doc1", ["c1"])
    eid1 = await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    eid2 = await upsert_entity(db, TENANT, "Bob", "person", "doc1", ["c1"])
    await upsert_relationship(
        db, TENANT, eid1, eid2, "knows", "Alice knows Bob", "doc1", ["c1"]
    )
    await upsert_community(db, TENANT, {
        "level": 0, "title": "Group", "summary": "s", "entity_ids": [],
    })

    stats = await get_graph_stats(db, TENANT)
    assert stats["entity_count"] == 2
    assert stats["relationship_count"] == 1
    assert stats["community_count"] == 1


# --- get_entity_neighbors ---


async def test_get_entity_neighbors_one_hop(db):
    eid_a = await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    eid_b = await upsert_entity(db, TENANT, "Bob", "person", "doc1", ["c1"])
    eid_c = await upsert_entity(db, TENANT, "Carol", "person", "doc1", ["c1"])

    await upsert_relationship(
        db, TENANT, eid_a, eid_b, "knows", "A knows B", "doc1", ["c1"]
    )
    await upsert_relationship(
        db, TENANT, eid_b, eid_c, "knows", "B knows C", "doc1", ["c1"]
    )

    neighbors = await get_entity_neighbors(db, TENANT, eid_a, max_hops=1)
    neighbor_names = {n["name"] for n in neighbors}
    assert "Bob" in neighbor_names
    # Carol is 2 hops away, should NOT appear for 1-hop
    assert "Carol" not in neighbor_names


# --- search_communities_by_embedding ---


async def test_search_communities_by_embedding(db):
    await upsert_community(db, TENANT, {
        "level": 0,
        "title": "Tech",
        "summary": "Tech stuff",
        "entity_ids": [],
        "summary_embedding": [1.0, 0.0, 0.0],
    })
    await upsert_community(db, TENANT, {
        "level": 0,
        "title": "Health",
        "summary": "Health stuff",
        "entity_ids": [],
        "summary_embedding": [0.0, 1.0, 0.0],
    })

    results = await search_communities_by_embedding(
        db, TENANT, [1.0, 0.0, 0.0], limit=1
    )
    assert len(results) == 1
    assert results[0]["title"] == "Tech"


# --- delete_doc_graph_data ---


async def test_delete_doc_graph_data_removes_orphans(db):
    # Create entities and relationships tied to doc1
    eid1 = await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    eid2 = await upsert_entity(db, TENANT, "Bob", "person", "doc1", ["c1"])
    await upsert_relationship(
        db, TENANT, eid1, eid2, "knows", "desc", "doc1", ["c1"]
    )

    # Delete doc1 graph data -- entities and rel should be removed (orphaned)
    await delete_doc_graph_data(db, TENANT, "doc1")

    stats = await get_graph_stats(db, TENANT)
    assert stats["entity_count"] == 0
    assert stats["relationship_count"] == 0


async def test_delete_doc_graph_data_preserves_shared_entities(db):
    # Entity referenced by doc1 AND doc2
    await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    await upsert_entity(db, TENANT, "Alice", "person", "doc2", ["c2"])

    # Delete only doc1 references
    await delete_doc_graph_data(db, TENANT, "doc1")

    stats = await get_graph_stats(db, TENANT)
    assert stats["entity_count"] == 1  # Alice should survive (still has doc2)

    entities = await find_entities_by_names(db, TENANT, ["Alice"])
    assert len(entities) == 1
    assert "doc2" in entities[0]["doc_ids"]
    assert "doc1" not in entities[0]["doc_ids"]
