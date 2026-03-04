from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from docingest.api.middleware import RateLimitHeaderMiddleware, RequestLoggingMiddleware
from docingest.api.routes import documents, health, search
from docingest.db.blob import close_blob, ensure_bucket, get_blob_client
from docingest.db.mongodb import close_db, ensure_indexes, get_db
from docingest.db.qdrant import close_qdrant
from docingest.db.redis import close_redis
from docingest.logging_config import configure_logging
from docingest.services.rate_limiter import close_rate_limiter, init_rate_limiter

configure_logging()

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting up")
    await init_rate_limiter()
    db = await get_db()
    await ensure_indexes(db)
    blob_client = get_blob_client()
    ensure_bucket(blob_client)
    yield
    log.info("shutting down")
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

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitHeaderMiddleware)

app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(documents.router, prefix="/v1", tags=["documents"])
app.include_router(search.router, prefix="/v1", tags=["search"])
