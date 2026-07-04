"""Graph RAG API routes for community detection and graph queries."""

import asyncio
import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from docingest.api.auth import AdminScope, ReadScope
from docingest.config import settings
from docingest.db.graph_store import (
    get_community_by_id,
    get_entity_by_id,
    list_communities,
    list_entities,
    search_communities_by_embedding,
)
from docingest.db.mongodb import get_db
from docingest.services.community_detection import build_communities
from docingest.services.embedding import embed_query

log = structlog.get_logger()

router = APIRouter(prefix="/graph", tags=["graph"])


# --- Response Models ---


class EntityResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    entity_type: str
    mention_count: int = 0
    doc_ids: list[str] = []
    chunk_ids: list[str] = []
    created_at: str
    updated_at: str


class EntityListResponse(BaseModel):
    entities: list[EntityResponse]
    total: int
    page: int
    per_page: int


class CommunitySummary(BaseModel):
    id: str
    level: int
    title: str
    summary: str
    entity_count: int = 0
    parent_community_id: str | None = None
    child_community_ids: list[str] = []
    created_at: str
    updated_at: str


class CommunityDetailResponse(BaseModel):
    id: str
    level: int
    title: str
    summary: str
    entity_count: int = 0
    entity_ids: list[str] = []
    parent_community_id: str | None = None
    child_community_ids: list[str] = []
    created_at: str
    updated_at: str
    member_entities: list[EntityResponse] = []


class CommunityListResponse(BaseModel):
    communities: list[CommunitySummary]
    total: int
    page: int
    per_page: int


class GraphSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=20)


class CommunityMatch(BaseModel):
    id: str
    title: str
    summary: str
    level: int
    score: float
    entity_ids: list[str] = []


class GraphSearchResponse(BaseModel):
    results: list[CommunityMatch]
    query_tokens: int
    search_time_ms: int


# --- Mapper Helpers ---


def _entity_to_response(doc: dict) -> EntityResponse:
    return EntityResponse(
        id=str(doc["_id"]),
        tenant_id=doc["tenant_id"],
        name=doc["name"],
        entity_type=doc["entity_type"],
        mention_count=doc.get("mention_count", 0),
        doc_ids=doc.get("doc_ids", []),
        chunk_ids=doc.get("chunk_ids", []),
        created_at=doc["created_at"].isoformat(),
        updated_at=doc["updated_at"].isoformat(),
    )


def _community_to_summary(doc: dict) -> CommunitySummary:
    return CommunitySummary(
        id=str(doc["_id"]),
        level=doc["level"],
        title=doc.get("title", ""),
        summary=doc.get("summary", ""),
        entity_count=len(doc.get("entity_ids", [])),
        parent_community_id=doc.get("parent_community_id"),
        child_community_ids=doc.get("child_community_ids", []),
        created_at=doc["created_at"].isoformat(),
        updated_at=doc["updated_at"].isoformat(),
    )


def _community_to_detail(doc: dict, members: list[EntityResponse]) -> CommunityDetailResponse:
    return CommunityDetailResponse(
        id=str(doc["_id"]),
        level=doc["level"],
        title=doc.get("title", ""),
        summary=doc.get("summary", ""),
        entity_count=len(doc.get("entity_ids", [])),
        entity_ids=[str(eid) for eid in doc.get("entity_ids", [])],
        parent_community_id=doc.get("parent_community_id"),
        child_community_ids=doc.get("child_community_ids", []),
        created_at=doc["created_at"].isoformat(),
        updated_at=doc["updated_at"].isoformat(),
        member_entities=members,
    )


# --- Routes ---


@router.post("/communities/rebuild")
async def rebuild_communities(
    tenant: AdminScope,
    db: AsyncIOMotorDatabase = Depends(get_db),  # noqa: B008
):
    """Rebuild community detection for the tenant's entity graph.

    Runs Leiden algorithm at configured resolution levels, generates
    extractive summaries, embeds them for search.
    """
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")

    log.info("community_rebuild_started", tenant_id=tenant["tenant_id"])
    stats = await build_communities(db, tenant["tenant_id"])
    log.info("community_rebuild_complete", tenant_id=tenant["tenant_id"], stats=stats)
    return {"status": "ok", "communities": stats}


@router.get("/entities")
async def list_entities_route(
    tenant: ReadScope,
    entity_type: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),  # noqa: B008
) -> EntityListResponse:
    """Paginated entity list with optional type filter and name search."""
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")
    docs, total = await list_entities(
        db, tenant["tenant_id"], entity_type=entity_type, q=q,
        page=page, per_page=per_page,
    )
    log.info(
        "graph_entities_list",
        tenant_id=tenant["tenant_id"], page=page, count=len(docs), total=total,
    )
    return EntityListResponse(
        entities=[_entity_to_response(d) for d in docs],
        total=total, page=page, per_page=per_page,
    )


@router.get("/entities/{entity_id}")
async def get_entity_detail(
    tenant: ReadScope,
    entity_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),  # noqa: B008
) -> EntityResponse:
    """Entity detail with tenant-scope enforcement."""
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")
    doc = await get_entity_by_id(db, entity_id, tenant_id=tenant["tenant_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Entity not found")
    log.info(
        "graph_entities_detail",
        tenant_id=tenant["tenant_id"], entity_id=entity_id,
    )
    return _entity_to_response(doc)


@router.get("/communities")
async def list_communities_route(
    tenant: ReadScope,
    level: int | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),  # noqa: B008
) -> CommunityListResponse:
    """Paginated community list with optional level filter."""
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")
    docs, total = await list_communities(
        db, tenant["tenant_id"], level=level, page=page, per_page=per_page,
    )
    log.info(
        "graph_communities_list",
        tenant_id=tenant["tenant_id"], level=level, page=page, count=len(docs), total=total,
    )
    return CommunityListResponse(
        communities=[_community_to_summary(d) for d in docs],
        total=total, page=page, per_page=per_page,
    )


@router.get("/communities/{community_id}")
async def get_community_detail(
    tenant: ReadScope,
    community_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),  # noqa: B008
) -> CommunityDetailResponse:
    """Community detail with expanded member entities."""
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")
    comm = await get_community_by_id(db, community_id, tenant["tenant_id"])
    if not comm:
        raise HTTPException(status_code=404, detail="Community not found")
    # Batch-fetch member entities
    member_docs = await asyncio.gather(*[
        get_entity_by_id(db, eid) for eid in comm.get("entity_ids", [])
    ])
    members = [_entity_to_response(d) for d in member_docs if d]
    log.info(
        "graph_communities_detail",
        tenant_id=tenant["tenant_id"], community_id=community_id,
        member_count=len(members),
    )
    return _community_to_detail(comm, members)


@router.post("/search")
async def graph_search(
    tenant: ReadScope,
    request: GraphSearchRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),  # noqa: B008
) -> GraphSearchResponse:
    """Embed query, rank tenant communities by cosine similarity, return top-k."""
    if not settings.graph_rag_enabled:
        raise HTTPException(status_code=403, detail="Graph RAG is not enabled")
    log.info("graph_search_started", tenant_id=tenant["tenant_id"], query=request.query)
    start = time.monotonic()
    loop = asyncio.get_running_loop()
    query_vector, token_count = await loop.run_in_executor(None, embed_query, request.query)
    scored_matches = await search_communities_by_embedding(
        db, tenant["tenant_id"], query_vector, limit=request.limit,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    results = [
        CommunityMatch(
            id=str(comm["_id"]),
            title=comm.get("title", ""),
            summary=comm.get("summary", ""),
            level=comm["level"],
            score=round(score, 4),
            entity_ids=[str(eid) for eid in comm.get("entity_ids", [])],
        )
        for score, comm in scored_matches
    ]
    log.info(
        "graph_search_complete",
        tenant_id=tenant["tenant_id"], result_count=len(results),
        search_time_ms=elapsed_ms,
    )
    return GraphSearchResponse(
        results=results, query_tokens=token_count, search_time_ms=elapsed_ms,
    )
