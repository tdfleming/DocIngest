import asyncio
import contextlib
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docingest.api.middleware import RateLimitHeaderMiddleware, RequestLoggingMiddleware
from docingest.api.routes import (
    admin,
    auth,
    billing,
    documents,
    graph,
    health,
    organizations,
    plans,
    search,
    usage,
)
from docingest.config import settings
from docingest.db.blob import close_blob, ensure_bucket, get_blob_client
from docingest.db.mongodb import close_db, ensure_indexes, get_db
from docingest.db.organizations import ensure_org_indexes
from docingest.db.qdrant import close_qdrant
from docingest.db.redis import close_redis
from docingest.db.subscriptions import ensure_subscription_indexes
from docingest.db.usage import ensure_usage_indexes
from docingest.logging_config import configure_logging
from docingest.services.rate_limiter import close_rate_limiter, init_rate_limiter
from docingest.services.telemetry import telemetry_loop

configure_logging()

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting up")
    await init_rate_limiter()
    db = await get_db()
    await ensure_indexes(db)
    await ensure_org_indexes(db)
    await ensure_usage_indexes(db)
    await ensure_subscription_indexes(db)
    blob_client = get_blob_client()
    ensure_bucket(blob_client)
    if settings.graph_rag_enabled:
        from docingest.db.graph_store import ensure_graph_indexes

        await ensure_graph_indexes(db)

    telemetry_task: asyncio.Task | None = None
    if settings.telemetry_enabled:
        telemetry_task = asyncio.create_task(telemetry_loop(db, settings))
        log.info("anonymous telemetry enabled", endpoint=settings.telemetry_endpoint)
    else:
        log.info("anonymous telemetry disabled")

    yield
    log.info("shutting down")
    if telemetry_task is not None:
        telemetry_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await telemetry_task
    await close_rate_limiter()
    await close_redis()
    await close_qdrant()
    close_blob()
    await close_db()


app = FastAPI(
    title="DocIngest",
    version="0.1.0",
    description="Multi-tenant document ingestion engine for RAG and semantic search",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)

app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(documents.router, prefix="/v1", tags=["documents"])
app.include_router(search.router, prefix="/v1", tags=["search"])
app.include_router(usage.router, prefix="/v1", tags=["usage"])
app.include_router(plans.router, prefix="/v1", tags=["plans"])
app.include_router(billing.router, prefix="/v1", tags=["billing"])
app.include_router(auth.router, prefix="/v1", tags=["auth"])
app.include_router(organizations.router, prefix="/v1", tags=["organizations"])
app.include_router(admin.router, prefix="/v1", tags=["admin"])
app.include_router(graph.router, prefix="/v1", tags=["graph"])
