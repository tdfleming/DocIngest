import asyncio

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from docingest.config import settings
from docingest.db.blob import get_blob_client
from docingest.db.mongodb import get_db
from docingest.db.qdrant import get_qdrant
from docingest.db.redis import get_redis_pool

router = APIRouter()
log = structlog.get_logger()


async def _check_mongodb() -> tuple[str, str]:
    try:
        db = await get_db()
        await db.command("ping")
        return "mongodb", "ok"
    except Exception as e:
        log.error("mongodb health check failed", error=str(e))
        return "mongodb", "error"


async def _check_qdrant() -> tuple[str, str]:
    try:
        qdrant = await get_qdrant()
        await qdrant.get_collections()
        return "qdrant", "ok"
    except Exception as e:
        log.error("qdrant health check failed", error=str(e))
        return "qdrant", "error"


async def _check_redis() -> tuple[str, str]:
    try:
        pool = await get_redis_pool()
        await pool.ping()
        return "redis", "ok"
    except Exception as e:
        log.error("redis health check failed", error=str(e))
        return "redis", "error"


async def _check_minio() -> tuple[str, str]:
    try:
        loop = asyncio.get_running_loop()
        client = get_blob_client()
        await loop.run_in_executor(None, client.bucket_exists, settings.minio_bucket)
        return "minio", "ok"
    except Exception as e:
        log.error("minio health check failed", error=str(e))
        return "minio", "error"


@router.get("/health")
async def health_check():
    results = await asyncio.gather(
        _check_mongodb(), _check_qdrant(), _check_redis(), _check_minio()
    )
    checks = dict(results)

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if overall == "healthy" else 503

    return JSONResponse(content={"status": overall, "checks": checks}, status_code=status_code)
