"""Integration tests for graph fields in DocumentResponse (GRAPH-WORKER-01, GRAPH-WORKER-04)."""

import os
from datetime import UTC, datetime

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from docingest.api.routes.documents import _doc_to_response
from docingest.db.mongodb import ensure_indexes, get_document, insert_document, list_documents
from docingest.models.document import ContentType, DocumentStatus, SourceType

TEST_DB_NAME = "docingest_test_documents_graph_response"
MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
TENANT = "test-tenant"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db():
    """Provide a clean test database for each test."""
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[TEST_DB_NAME]
    await ensure_indexes(database)
    yield database
    await client.drop_database(TEST_DB_NAME)
    client.close()


@pytest.fixture()
async def seed_doc(db):
    """Insert a minimal document record without graph fields; return its string ID."""
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
async def seed_doc_with_graph(db):
    """Insert a document record with graph fields populated; return its string ID."""
    doc_fields = {
        "tenant_id": TENANT,
        "source_type": SourceType.UPLOAD,
        "source_ref": "graphtest.pdf",
        "content_type": ContentType.PDF,
        "status": DocumentStatus.COMPLETE,
        "blob_path": "raw/graphtest.pdf",
        "file_size_bytes": 2048,
        "chunk_count": 4,
        "version": 1,
        "source_hash": "cafebabe" * 8,
        "graph_status": "complete",
        "entity_count": 5,
        "relationship_count": 3,
        "graph_built_at": datetime.now(UTC),
    }
    return await insert_document(db, doc_fields)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_get_document_returns_graph_defaults(db, seed_doc):
    """Non-graph-built doc returns graph_status=None, entity_count=0, etc."""
    doc = await get_document(db, seed_doc, TENANT)
    response = _doc_to_response(doc)

    assert response.graph_status is None
    assert response.entity_count == 0
    assert response.relationship_count == 0
    assert response.graph_built_at is None

    # Existing fields remain correct
    assert response.id == seed_doc
    assert response.status == "complete"
    assert response.chunk_count == 2


async def test_get_document_returns_graph_populated(db, seed_doc_with_graph):
    """Graph-built doc returns actual values including ISO timestamp string."""
    doc = await get_document(db, seed_doc_with_graph, TENANT)
    response = _doc_to_response(doc)

    assert response.graph_status == "complete"
    assert response.entity_count == 5
    assert response.relationship_count == 3
    assert response.graph_built_at is not None
    assert isinstance(response.graph_built_at, str)
    assert "T" in response.graph_built_at  # basic ISO 8601 format check


async def test_list_documents_returns_graph_fields(db, seed_doc_with_graph):
    """list_documents result includes all 4 graph fields via _doc_to_response."""
    docs, total = await list_documents(db, TENANT)

    assert total >= 1
    response = _doc_to_response(docs[0])

    assert response.graph_status == "complete"
    assert response.entity_count == 5
    assert response.relationship_count == 3
    assert response.graph_built_at is not None
    assert isinstance(response.graph_built_at, str)
    assert "T" in response.graph_built_at


async def test_graph_fields_present_when_graph_disabled(db, seed_doc):
    """Fields are present with defaults regardless of graph_rag_enabled setting.

    _doc_to_response has no conditional logic on graph_rag_enabled — fields are always
    present per D-05/D-06. This test proves that by calling the mapper directly.
    """
    doc = await get_document(db, seed_doc, TENANT)
    response = _doc_to_response(doc)

    # Defaults match D-03
    assert response.graph_status is None
    assert response.entity_count == 0
    assert response.relationship_count == 0
    assert response.graph_built_at is None

    # Fields exist on the model regardless of runtime settings
    assert hasattr(response, "graph_status")
    assert hasattr(response, "entity_count")
    assert hasattr(response, "relationship_count")
    assert hasattr(response, "graph_built_at")
