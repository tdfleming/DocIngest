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


@router.get("/health")
async def health_check():
    checks = {}

    try:
        db = await get_db()
        await db.command("ping")
        checks["mongodb"] = "ok"
    except Exception as e:
        log.error("mongodb health check failed", error=str(e))
        checks["mongodb"] = "error"

    try:
        qdrant = await get_qdrant()
        await qdrant.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        log.error("qdrant health check failed", error=str(e))
        checks["qdrant"] = "error"

    try:
        pool = await get_redis_pool()
        await pool.ping()
        checks["redis"] = "ok"
    except Exception as e:
        log.error("redis health check failed", error=str(e))
        checks["redis"] = "error"

    try:
        client = get_blob_client()
        client.bucket_exists(settings.minio_bucket)
        checks["minio"] = "ok"
    except Exception as e:
        log.error("minio health check failed", error=str(e))
        checks["minio"] = "error"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if overall == "healthy" else 503

    return JSONResponse(content={"status": overall, "checks": checks}, status_code=status_code)
