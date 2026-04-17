"""Integration tests for graph API routes (16-01).

Covers entity list/detail, community list/detail, and graph search.
Calls route handler functions directly (not via httpx.AsyncClient) with real MongoDB.
Monkeypatches settings.graph_rag_enabled and embed_query as needed.
"""

import os

import pytest
from bson import ObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.api.routes.graph import (
    GraphSearchRequest,
    get_community_detail,
    get_entity_detail,
    graph_search,
    list_communities_route,
    list_entities_route,
)
from docingest.db.graph_store import (
    ensure_graph_indexes,
    upsert_community,
    upsert_entity,
)

TEST_DB_NAME = "docingest_test_graph_api"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
TENANT = "test-tenant"
OTHER_TENANT = "other-tenant"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db():
    """Provide a clean test database for each test."""
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_graph_indexes(database)
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


def _fake_tenant(tenant_id: str = TENANT) -> dict:
    return {"tenant_id": tenant_id, "key_id": "test-key"}


def _enable_graph(monkeypatch) -> None:
    monkeypatch.setattr("docingest.api.routes.graph.settings.graph_rag_enabled", True)


def _disable_graph(monkeypatch) -> None:
    monkeypatch.setattr("docingest.api.routes.graph.settings.graph_rag_enabled", False)


def _fake_embed_query(text: str):
    """Returns a dummy 384-dim vector and token count without loading the model."""
    return [0.1] * 384, len(text) // 4


async def _seed_entities(db):
    """Seed 3 entities: Alice (person), Bob (person), Acme Corp (organization). Return IDs."""
    eid_alice = await upsert_entity(db, TENANT, "Alice", "person", "doc1", ["c1"])
    eid_bob = await upsert_entity(db, TENANT, "Bob", "person", "doc1", ["c2"])
    eid_acme = await upsert_entity(db, TENANT, "Acme Corp", "organization", "doc1", ["c3"])
    return eid_alice, eid_bob, eid_acme


async def _seed_other_entity(db):
    """Seed 1 entity for OTHER_TENANT. Return ID."""
    return await upsert_entity(db, OTHER_TENANT, "Evil Corp", "organization", "doc99", ["cx"])


async def _seed_communities(db, entity_ids: list[str]):
    """Seed 3 communities for TENANT. Return IDs."""
    cid_1 = await upsert_community(db, TENANT, {
        "level": 0,
        "title": "Alpha",
        "summary": "Alpha community summary",
        "entity_ids": entity_ids[:2],
        "summary_embedding": [0.1] * 384,
    })
    cid_2 = await upsert_community(db, TENANT, {
        "level": 0,
        "title": "Beta",
        "summary": "Beta community summary",
        "entity_ids": entity_ids[2:],
        "summary_embedding": [0.2] * 384,
    })
    cid_3 = await upsert_community(db, TENANT, {
        "level": 1,
        "title": "Gamma",
        "summary": "Gamma top-level community",
        "entity_ids": entity_ids,
        "summary_embedding": [0.3] * 384,
    })
    return cid_1, cid_2, cid_3


async def _seed_other_community(db):
    """Seed 1 community for OTHER_TENANT. Return ID."""
    return await upsert_community(db, OTHER_TENANT, {
        "level": 0,
        "title": "Other",
        "summary": "Other tenant community",
        "entity_ids": [],
    })


# ---------------------------------------------------------------------------
# Test 1: entity list pagination
# ---------------------------------------------------------------------------


async def test_entity_list_pagination(db, monkeypatch):
    """Entity list returns paginated results with correct total, page, per_page."""
    _enable_graph(monkeypatch)
    await _seed_entities(db)

    response = await list_entities_route(
        tenant=_fake_tenant(), page=1, per_page=2, db=db,
    )
    assert response.total == 3
    assert len(response.entities) == 2
    assert response.page == 1
    assert response.per_page == 2

    response2 = await list_entities_route(
        tenant=_fake_tenant(), page=2, per_page=2, db=db,
    )
    assert response2.total == 3
    assert len(response2.entities) == 1
    assert response2.page == 2


# ---------------------------------------------------------------------------
# Test 2: entity list filter by entity_type
# ---------------------------------------------------------------------------


async def test_entity_list_filter_by_type(db, monkeypatch):
    """Entity list with entity_type filter narrows results correctly."""
    _enable_graph(monkeypatch)
    await _seed_entities(db)

    response = await list_entities_route(
        tenant=_fake_tenant(), entity_type="person", page=1, per_page=50, db=db,
    )
    assert response.total == 2
    names = {e.name for e in response.entities}
    assert "Alice" in names
    assert "Bob" in names
    assert "Acme Corp" not in names


# ---------------------------------------------------------------------------
# Test 3: entity list name search (case-insensitive)
# ---------------------------------------------------------------------------


async def test_entity_list_search_q(db, monkeypatch):
    """Entity list with q param performs case-insensitive name substring search."""
    _enable_graph(monkeypatch)
    await _seed_entities(db)

    response = await list_entities_route(
        tenant=_fake_tenant(), q="ali", page=1, per_page=50, db=db,
    )
    assert response.total == 1
    assert response.entities[0].name == "Alice"


# ---------------------------------------------------------------------------
# Test 4: entity list regex metachar safety
# ---------------------------------------------------------------------------


async def test_entity_list_search_regex_metachar(db, monkeypatch):
    """Entity list with regex metachar in q does not crash (re.escape works)."""
    _enable_graph(monkeypatch)
    await _seed_entities(db)

    # This would cause a MongoDB regex error without re.escape
    response = await list_entities_route(
        tenant=_fake_tenant(), q="a.b*", page=1, per_page=50, db=db,
    )
    # 0 results is fine — what matters is no exception
    assert isinstance(response.total, int)
    assert response.total >= 0


# ---------------------------------------------------------------------------
# Test 5: entity detail success
# ---------------------------------------------------------------------------


async def test_entity_detail_success(db, monkeypatch):
    """Entity detail returns correct fields with no embedding key."""
    _enable_graph(monkeypatch)
    eid_alice, _, _ = await _seed_entities(db)

    response = await get_entity_detail(
        tenant=_fake_tenant(), entity_id=eid_alice, db=db,
    )
    assert response.id == eid_alice
    assert response.name == "Alice"
    assert response.entity_type == "person"
    assert response.tenant_id == TENANT
    assert isinstance(response.created_at, str)
    assert isinstance(response.updated_at, str)
    # No embedding field on the response model
    assert not hasattr(response, "embedding")


# ---------------------------------------------------------------------------
# Test 6: entity detail cross-tenant returns 404
# ---------------------------------------------------------------------------


async def test_entity_detail_cross_tenant_404(db, monkeypatch):
    """Entity detail with other-tenant entity_id returns 404 (not 403)."""
    _enable_graph(monkeypatch)
    other_eid = await _seed_other_entity(db)

    with pytest.raises(HTTPException) as exc_info:
        await get_entity_detail(
            tenant=_fake_tenant(TENANT), entity_id=other_eid, db=db,
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Test 7: entity detail nonexistent returns 404
# ---------------------------------------------------------------------------


async def test_entity_detail_nonexistent_404(db, monkeypatch):
    """Entity detail with fabricated ObjectId returns 404."""
    _enable_graph(monkeypatch)
    fake_id = str(ObjectId())

    with pytest.raises(HTTPException) as exc_info:
        await get_entity_detail(
            tenant=_fake_tenant(), entity_id=fake_id, db=db,
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Test 8: community list pagination and sort
# ---------------------------------------------------------------------------


async def test_community_list_pagination_and_sort(db, monkeypatch):
    """Community list returns paginated results sorted by (level, title)."""
    _enable_graph(monkeypatch)
    eid_alice, eid_bob, eid_acme = await _seed_entities(db)
    await _seed_communities(db, [eid_alice, eid_bob, eid_acme])

    response = await list_communities_route(
        tenant=_fake_tenant(), level=None, page=1, per_page=2, db=db,
    )
    assert response.total == 3
    assert len(response.communities) == 2
    assert response.page == 1
    assert response.per_page == 2

    # First two items should be level 0, alphabetically: Alpha before Beta
    assert response.communities[0].level == 0
    assert response.communities[0].title == "Alpha"
    assert response.communities[1].level == 0
    assert response.communities[1].title == "Beta"

    response2 = await list_communities_route(
        tenant=_fake_tenant(), level=None, page=2, per_page=2, db=db,
    )
    assert response2.total == 3
    assert len(response2.communities) == 1
    assert response2.communities[0].title == "Gamma"


# ---------------------------------------------------------------------------
# Test 9: community list level filter
# ---------------------------------------------------------------------------


async def test_community_list_level_filter(db, monkeypatch):
    """Community list with level filter narrows to single level."""
    _enable_graph(monkeypatch)
    eid_alice, eid_bob, eid_acme = await _seed_entities(db)
    await _seed_communities(db, [eid_alice, eid_bob, eid_acme])

    response = await list_communities_route(
        tenant=_fake_tenant(), level=0, page=1, per_page=50, db=db,
    )
    assert response.total == 2
    assert all(c.level == 0 for c in response.communities)

    response1 = await list_communities_route(
        tenant=_fake_tenant(), level=1, page=1, per_page=50, db=db,
    )
    assert response1.total == 1
    assert response1.communities[0].title == "Gamma"


# ---------------------------------------------------------------------------
# Test 10: community detail with expanded member_entities
# ---------------------------------------------------------------------------


async def test_community_detail_with_members(db, monkeypatch):
    """Community detail returns full community with expanded member_entities."""
    _enable_graph(monkeypatch)
    eid_alice, eid_bob, _ = await _seed_entities(db)
    cid_1, _, _ = await _seed_communities(db, [eid_alice, eid_bob])

    response = await get_community_detail(
        tenant=_fake_tenant(), community_id=cid_1, db=db,
    )
    assert response.id == cid_1
    assert response.title == "Alpha"
    assert response.level == 0
    assert len(response.member_entities) == 2
    member_names = {m.name for m in response.member_entities}
    assert "Alice" in member_names
    assert "Bob" in member_names
    # entity_ids list present
    assert len(response.entity_ids) == 2
    # No summary_embedding on detail response
    assert not hasattr(response, "summary_embedding")


# ---------------------------------------------------------------------------
# Test 11: community detail cross-tenant returns 404
# ---------------------------------------------------------------------------


async def test_community_detail_cross_tenant_404(db, monkeypatch):
    """Community detail with other-tenant community_id returns 404."""
    _enable_graph(monkeypatch)
    other_cid = await _seed_other_community(db)

    with pytest.raises(HTTPException) as exc_info:
        await get_community_detail(
            tenant=_fake_tenant(TENANT), community_id=other_cid, db=db,
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Test 12: graph search returns ranked communities
# ---------------------------------------------------------------------------


async def test_graph_search_returns_ranked(db, monkeypatch):
    """Graph search returns ranked communities with scores."""
    _enable_graph(monkeypatch)
    monkeypatch.setattr("docingest.api.routes.graph.embed_query", _fake_embed_query)

    eid_alice, eid_bob, eid_acme = await _seed_entities(db)
    await _seed_communities(db, [eid_alice, eid_bob, eid_acme])

    request = GraphSearchRequest(query="technology companies", limit=5)
    response = await graph_search(
        tenant=_fake_tenant(), request=request, db=db,
    )
    assert isinstance(response.results, list)
    assert len(response.results) > 0
    assert response.query_tokens > 0
    assert response.search_time_ms >= 0

    # All results have expected fields
    for result in response.results:
        assert isinstance(result.score, float)
        assert isinstance(result.id, str)
        assert isinstance(result.title, str)


# ---------------------------------------------------------------------------
# Test 13: graph search on empty tenant returns empty results
# ---------------------------------------------------------------------------


async def test_graph_search_empty_tenant(db, monkeypatch):
    """Graph search on tenant with no communities returns empty results."""
    _enable_graph(monkeypatch)
    monkeypatch.setattr("docingest.api.routes.graph.embed_query", _fake_embed_query)

    request = GraphSearchRequest(query="something", limit=5)
    response = await graph_search(
        tenant=_fake_tenant(), request=request, db=db,
    )
    assert response.results == []
    assert response.query_tokens > 0


# ---------------------------------------------------------------------------
# Test 14: gating returns 403 when graph_rag_enabled=False
# ---------------------------------------------------------------------------


async def test_gating_returns_403(db, monkeypatch):
    """All 5 route endpoints return 403 when graph_rag_enabled is False."""
    _disable_graph(monkeypatch)
    monkeypatch.setattr("docingest.api.routes.graph.embed_query", _fake_embed_query)

    tenant = _fake_tenant()
    fake_id = str(ObjectId())

    with pytest.raises(HTTPException) as exc_info:
        await list_entities_route(tenant=tenant, page=1, per_page=50, db=db)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await get_entity_detail(tenant=tenant, entity_id=fake_id, db=db)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await list_communities_route(tenant=tenant, level=None, page=1, per_page=50, db=db)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await get_community_detail(tenant=tenant, community_id=fake_id, db=db)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await graph_search(
            tenant=tenant, request=GraphSearchRequest(query="test"), db=db,
        )
    assert exc_info.value.status_code == 403
