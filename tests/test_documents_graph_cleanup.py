"""Integration tests for graph cleanup wiring in documents.py (GRAPH-06, GRAPH-WORKER-03)."""

import os

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from structlog.testing import capture_logs

from docingest.api.routes.documents import delete_document_route, reprocess_document
from docingest.db.graph_store import (
    ensure_graph_indexes,
    find_entities_by_names,
    get_graph_stats,
    upsert_entity,
    upsert_relationship,
)
from docingest.db.mongodb import insert_document
from docingest.models.document import ContentType, DocumentStatus, SourceType

TEST_DB_NAME = "docingest_test_documents_graph_cleanup"
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


@pytest.fixture()
async def seed_doc(db):
    """Insert a minimal document record into MongoDB; return its string ID."""
    doc_fields = {
        "tenant_id": TENANT,
        "source_type": SourceType.UPLOAD,
        "source_ref": "test.pdf",
        "content_type": ContentType.PDF,
        "status": DocumentStatus.COMPLETE,
        "blob_path": "raw/abc123.pdf",
        "file_size_bytes": 1024,
        "chunk_count": 2,
        "version": 1,
        "source_hash": "deadbeef" * 8,
    }
    return await insert_document(db, doc_fields)


@pytest.fixture()
def fake_request():
    """Return a minimal object that satisfies `request.state` usage in reprocess_document."""

    class _FakeState:
        trace_id = "test-trace-id"

    class _FakeRequest:
        state = _FakeState()

    return _FakeRequest()


@pytest.fixture()
def fake_tenant():
    """Return a minimal Tenant-compatible dict."""
    return {"tenant_id": TENANT, "key_id": "test-key-id"}


# ---------------------------------------------------------------------------
# Positive tests — graph_rag_enabled = True
# ---------------------------------------------------------------------------


async def test_delete_route_cleans_graph_data_when_enabled(db, seed_doc, fake_tenant, monkeypatch):
    """DELETE route removes entities and relationships synchronously when graph RAG is enabled."""
    monkeypatch.setattr("docingest.api.routes.documents.settings.graph_rag_enabled", True)

    # Patch out infrastructure calls that are not under test
    async def _noop_get_qdrant():
        return None

    async def _noop_delete_chunks(*args, **kwargs):
        pass

    async def _noop_delete_blob(*args, **kwargs):
        pass

    monkeypatch.setattr("docingest.api.routes.documents.get_qdrant", _noop_get_qdrant)
    monkeypatch.setattr("docingest.api.routes.documents.delete_doc_chunks", _noop_delete_chunks)
    monkeypatch.setattr("docingest.api.routes.documents.get_db", lambda: _async_return(db))
    monkeypatch.setattr("docingest.api.routes.documents.get_blob_client", lambda: None)
    monkeypatch.setattr(
        "docingest.api.routes.documents.delete_blob",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "docingest.api.routes.documents.delete_document",
        lambda *a, **kw: _async_return(None),
    )

    # Seed graph data
    eid1 = await upsert_entity(db, TENANT, "Alice", "person", seed_doc, ["c1"])
    eid2 = await upsert_entity(db, TENANT, "Bob", "person", seed_doc, ["c1"])
    await upsert_relationship(db, TENANT, eid1, eid2, "knows", "desc", seed_doc, ["c1"])

    pre_stats = await get_graph_stats(db, TENANT)
    assert pre_stats["entity_count"] == 2
    assert pre_stats["relationship_count"] == 1

    # Call route directly
    response = await delete_document_route(tenant=fake_tenant, doc_id=seed_doc)

    assert response == {"id": seed_doc, "status": "deleted"}
    post_stats = await get_graph_stats(db, TENANT)
    assert post_stats["entity_count"] == 0
    assert post_stats["relationship_count"] == 0


async def test_reprocess_route_cleans_graph_data_when_enabled(
    db, seed_doc, fake_tenant, fake_request, monkeypatch
):
    """Reprocess route removes entities and relationships synchronously (before worker runs)."""
    monkeypatch.setattr("docingest.api.routes.documents.settings.graph_rag_enabled", True)

    async def _noop_get_qdrant():
        return None

    async def _noop_delete_chunks(*args, **kwargs):
        pass

    async def _noop_increment_version(*args, **kwargs):
        pass

    async def _noop_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr("docingest.api.routes.documents.get_qdrant", _noop_get_qdrant)
    monkeypatch.setattr("docingest.api.routes.documents.delete_doc_chunks", _noop_delete_chunks)
    monkeypatch.setattr("docingest.api.routes.documents.get_db", lambda: _async_return(db))
    monkeypatch.setattr(
        "docingest.api.routes.documents.increment_version", _noop_increment_version
    )
    monkeypatch.setattr("docingest.api.routes.documents._enqueue_conversion", _noop_enqueue)

    # Seed graph data
    eid1 = await upsert_entity(db, TENANT, "Alice", "person", seed_doc, ["c1"])
    eid2 = await upsert_entity(db, TENANT, "Bob", "person", seed_doc, ["c1"])
    await upsert_relationship(db, TENANT, eid1, eid2, "knows", "desc", seed_doc, ["c1"])

    pre_stats = await get_graph_stats(db, TENANT)
    assert pre_stats["entity_count"] == 2

    # Call route directly
    response = await reprocess_document(
        request=fake_request, tenant=fake_tenant, doc_id=seed_doc
    )

    assert response["status"] == "pending"
    assert response["id"] == seed_doc

    post_stats = await get_graph_stats(db, TENANT)
    assert post_stats["entity_count"] == 0
    assert post_stats["relationship_count"] == 0


# ---------------------------------------------------------------------------
# Negative tests — graph_rag_enabled = False
# ---------------------------------------------------------------------------


async def test_delete_route_skips_graph_cleanup_when_disabled(
    db, seed_doc, fake_tenant, monkeypatch
):
    """DELETE route does NOT touch graph data when graph RAG is disabled."""
    monkeypatch.setattr("docingest.api.routes.documents.settings.graph_rag_enabled", False)

    async def _noop_get_qdrant():
        return None

    async def _noop_delete_chunks(*args, **kwargs):
        pass

    monkeypatch.setattr("docingest.api.routes.documents.get_qdrant", _noop_get_qdrant)
    monkeypatch.setattr("docingest.api.routes.documents.delete_doc_chunks", _noop_delete_chunks)
    monkeypatch.setattr("docingest.api.routes.documents.get_db", lambda: _async_return(db))
    monkeypatch.setattr("docingest.api.routes.documents.get_blob_client", lambda: None)
    monkeypatch.setattr("docingest.api.routes.documents.delete_blob", lambda *a, **kw: None)
    monkeypatch.setattr(
        "docingest.api.routes.documents.delete_document",
        lambda *a, **kw: _async_return(None),
    )

    # Seed graph data
    eid1 = await upsert_entity(db, TENANT, "Alice", "person", seed_doc, ["c1"])
    eid2 = await upsert_entity(db, TENANT, "Bob", "person", seed_doc, ["c1"])
    await upsert_relationship(db, TENANT, eid1, eid2, "knows", "desc", seed_doc, ["c1"])

    # Call route with graph disabled
    await delete_document_route(tenant=fake_tenant, doc_id=seed_doc)

    # Graph data should still exist — gate prevented cleanup
    post_stats = await get_graph_stats(db, TENANT)
    assert post_stats["entity_count"] == 2
    assert post_stats["relationship_count"] == 1


async def test_reprocess_route_skips_graph_cleanup_when_disabled(
    db, seed_doc, fake_tenant, fake_request, monkeypatch
):
    """Reprocess route does NOT touch graph data when graph RAG is disabled."""
    monkeypatch.setattr("docingest.api.routes.documents.settings.graph_rag_enabled", False)

    async def _noop_get_qdrant():
        return None

    async def _noop_delete_chunks(*args, **kwargs):
        pass

    async def _noop_increment_version(*args, **kwargs):
        pass

    async def _noop_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr("docingest.api.routes.documents.get_qdrant", _noop_get_qdrant)
    monkeypatch.setattr("docingest.api.routes.documents.delete_doc_chunks", _noop_delete_chunks)
    monkeypatch.setattr("docingest.api.routes.documents.get_db", lambda: _async_return(db))
    monkeypatch.setattr(
        "docingest.api.routes.documents.increment_version", _noop_increment_version
    )
    monkeypatch.setattr("docingest.api.routes.documents._enqueue_conversion", _noop_enqueue)

    # Seed graph data
    eid1 = await upsert_entity(db, TENANT, "Alice", "person", seed_doc, ["c1"])
    eid2 = await upsert_entity(db, TENANT, "Bob", "person", seed_doc, ["c1"])
    await upsert_relationship(db, TENANT, eid1, eid2, "knows", "desc", seed_doc, ["c1"])

    # Call route with graph disabled
    await reprocess_document(request=fake_request, tenant=fake_tenant, doc_id=seed_doc)

    # Graph data should still exist — gate prevented cleanup
    post_stats = await get_graph_stats(db, TENANT)
    assert post_stats["entity_count"] == 2
    assert post_stats["relationship_count"] == 1


# ---------------------------------------------------------------------------
# Shared-entity preservation test
# ---------------------------------------------------------------------------


async def test_delete_route_preserves_shared_entities(
    db, fake_tenant, monkeypatch
):
    """Entity shared by two docs survives when only one doc is deleted."""
    monkeypatch.setattr("docingest.api.routes.documents.settings.graph_rag_enabled", True)

    async def _noop_get_qdrant():
        return None

    async def _noop_delete_chunks(*args, **kwargs):
        pass

    monkeypatch.setattr("docingest.api.routes.documents.get_qdrant", _noop_get_qdrant)
    monkeypatch.setattr("docingest.api.routes.documents.delete_doc_chunks", _noop_delete_chunks)
    monkeypatch.setattr("docingest.api.routes.documents.get_blob_client", lambda: None)
    monkeypatch.setattr("docingest.api.routes.documents.delete_blob", lambda *a, **kw: None)
    monkeypatch.setattr(
        "docingest.api.routes.documents.delete_document",
        lambda *a, **kw: _async_return(None),
    )

    # Insert TWO document records
    doc_fields_1 = {
        "tenant_id": TENANT,
        "source_type": SourceType.UPLOAD,
        "source_ref": "doc1.pdf",
        "content_type": ContentType.PDF,
        "status": DocumentStatus.COMPLETE,
        "blob_path": "raw/doc1.pdf",
        "file_size_bytes": 512,
        "chunk_count": 1,
        "version": 1,
        "source_hash": "aabbccdd" * 8,
    }
    doc_fields_2 = {
        "tenant_id": TENANT,
        "source_type": SourceType.UPLOAD,
        "source_ref": "doc2.pdf",
        "content_type": ContentType.PDF,
        "status": DocumentStatus.COMPLETE,
        "blob_path": "raw/doc2.pdf",
        "file_size_bytes": 512,
        "chunk_count": 1,
        "version": 1,
        "source_hash": "11223344" * 8,
    }
    doc_id_1 = await insert_document(db, doc_fields_1)
    doc_id_2 = await insert_document(db, doc_fields_2)

    # Seed Alice referenced by BOTH docs
    await upsert_entity(db, TENANT, "Alice", "person", doc_id_1, ["c1"])
    await upsert_entity(db, TENANT, "Alice", "person", doc_id_2, ["c2"])

    pre_stats = await get_graph_stats(db, TENANT)
    assert pre_stats["entity_count"] == 1  # deduped on name+type

    # Delete doc1 via the route
    monkeypatch.setattr(
        "docingest.api.routes.documents.get_db", lambda: _async_return(db)
    )
    await delete_document_route(tenant=fake_tenant, doc_id=doc_id_1)

    # Alice should survive (still referenced by doc2)
    post_stats = await get_graph_stats(db, TENANT)
    assert post_stats["entity_count"] == 1

    entities = await find_entities_by_names(db, TENANT, ["Alice"])
    assert len(entities) == 1
    assert doc_id_2 in entities[0]["doc_ids"]
    assert doc_id_1 not in entities[0]["doc_ids"]


# ---------------------------------------------------------------------------
# Lenient error tests (Task 3 — appended below)
# ---------------------------------------------------------------------------


async def test_delete_route_lenient_on_graph_cleanup_failure(
    db, seed_doc, fake_tenant, monkeypatch
):
    """DELETE route returns 200 and logs graph_cleanup_failed when delete_doc_graph_data raises."""
    monkeypatch.setattr("docingest.api.routes.documents.settings.graph_rag_enabled", True)

    async def _boom(*args, **kwargs):
        raise RuntimeError("mongo exploded")

    monkeypatch.setattr("docingest.api.routes.documents.delete_doc_graph_data", _boom)

    async def _noop_get_qdrant():
        return None

    async def _noop_delete_chunks(*args, **kwargs):
        pass

    monkeypatch.setattr("docingest.api.routes.documents.get_qdrant", _noop_get_qdrant)
    monkeypatch.setattr("docingest.api.routes.documents.delete_doc_chunks", _noop_delete_chunks)
    monkeypatch.setattr("docingest.api.routes.documents.get_db", lambda: _async_return(db))
    monkeypatch.setattr("docingest.api.routes.documents.get_blob_client", lambda: None)
    monkeypatch.setattr("docingest.api.routes.documents.delete_blob", lambda *a, **kw: None)
    monkeypatch.setattr(
        "docingest.api.routes.documents.delete_document",
        lambda *a, **kw: _async_return(None),
    )

    with capture_logs() as logs:
        response = await delete_document_route(tenant=fake_tenant, doc_id=seed_doc)

    assert response == {"id": seed_doc, "status": "deleted"}

    cleanup_logs = [e for e in logs if e.get("event") == "graph_cleanup_failed"]
    assert len(cleanup_logs) == 1
    assert cleanup_logs[0]["doc_id"] == seed_doc
    assert cleanup_logs[0]["tenant_id"] == TENANT
    assert "mongo exploded" in cleanup_logs[0].get("error", "")


async def test_reprocess_route_lenient_on_graph_cleanup_failure(
    db, seed_doc, fake_tenant, fake_request, monkeypatch
):
    """Reprocess route returns 202 and logs graph_cleanup_failed when delete_doc_graph_data raises."""  # noqa: E501
    monkeypatch.setattr("docingest.api.routes.documents.settings.graph_rag_enabled", True)

    async def _boom(*args, **kwargs):
        raise RuntimeError("mongo exploded")

    monkeypatch.setattr("docingest.api.routes.documents.delete_doc_graph_data", _boom)

    async def _noop_get_qdrant():
        return None

    async def _noop_delete_chunks(*args, **kwargs):
        pass

    async def _noop_increment_version(*args, **kwargs):
        pass

    async def _noop_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr("docingest.api.routes.documents.get_qdrant", _noop_get_qdrant)
    monkeypatch.setattr("docingest.api.routes.documents.delete_doc_chunks", _noop_delete_chunks)
    monkeypatch.setattr("docingest.api.routes.documents.get_db", lambda: _async_return(db))
    monkeypatch.setattr(
        "docingest.api.routes.documents.increment_version", _noop_increment_version
    )
    monkeypatch.setattr("docingest.api.routes.documents._enqueue_conversion", _noop_enqueue)

    with capture_logs() as logs:
        response = await reprocess_document(
            request=fake_request, tenant=fake_tenant, doc_id=seed_doc
        )

    assert response["status"] == "pending"
    assert response["id"] == seed_doc

    cleanup_logs = [e for e in logs if e.get("event") == "graph_cleanup_failed"]
    assert len(cleanup_logs) == 1
    assert cleanup_logs[0]["doc_id"] == seed_doc
    assert cleanup_logs[0]["tenant_id"] == TENANT
    assert "mongo exploded" in cleanup_logs[0].get("error", "")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _async_return(value):
    """Awaitable that immediately returns value — used to wrap sync mocks."""
    return value
