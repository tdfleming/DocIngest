"""Graph RAG API routes for community detection and graph queries."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from docingest.api.auth import Tenant
from docingest.config import settings
from docingest.db.mongodb import get_db
from docingest.services.community_detection import build_communities

log = structlog.get_logger()

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/communities/rebuild")
async def rebuild_communities(
    tenant: Tenant = Depends(),  # noqa: B008
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
