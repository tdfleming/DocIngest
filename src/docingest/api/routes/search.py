import asyncio
import time

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from docingest.api.auth import ReadScope
from docingest.db.qdrant import get_qdrant, search_chunks
from docingest.services.embedding import embed_query
from docingest.services.reranker import rerank

router = APIRouter()
log = structlog.get_logger()


class SearchFilters(BaseModel):
    content_type: list[str] | None = None
    source_ref: str | None = None


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=100)
    filters: SearchFilters | None = None
    rerank: bool = True


class SearchResult(BaseModel):
    chunk_text: str
    score: float
    doc_id: str
    source_ref: str
    content_type: str
    heading_chain: list[str]
    chunk_index: int


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query_tokens: int
    search_time_ms: int


@router.post("/search")
async def semantic_search(tenant: ReadScope, request: SearchRequest):
    start = time.monotonic()

    loop = asyncio.get_running_loop()
    query_vector, token_count = await loop.run_in_executor(None, embed_query, request.query)

    # Retrieve more candidates when reranking
    retrieve_limit = request.limit * 3 if request.rerank else request.limit

    # Build Qdrant filters
    qdrant_filters = {}
    if request.filters:
        if request.filters.content_type:
            qdrant_filters["content_type"] = request.filters.content_type
        if request.filters.source_ref:
            qdrant_filters["source_ref"] = request.filters.source_ref

    qdrant = await get_qdrant()
    raw_results = await search_chunks(
        qdrant, tenant["tenant_id"], query_vector, retrieve_limit, qdrant_filters or None
    )

    results = [
        SearchResult(
            chunk_text=r.payload["chunk_text"],
            score=r.score,
            doc_id=r.payload["doc_id"],
            source_ref=r.payload.get("source_ref", ""),
            content_type=r.payload.get("content_type", ""),
            heading_chain=r.payload.get("heading_chain", []),
            chunk_index=r.payload.get("chunk_index", 0),
        )
        for r in raw_results
    ]

    if request.rerank and results:
        results = await rerank(request.query, results, request.limit)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return SearchResponse(
        results=results[: request.limit],
        query_tokens=token_count,
        search_time_ms=elapsed_ms,
    )
