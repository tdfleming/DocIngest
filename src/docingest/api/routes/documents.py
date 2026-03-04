import hashlib
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field, HttpUrl

from fastapi.responses import PlainTextResponse

from docingest.api.auth import Tenant
from docingest.db.blob import delete_blob, download_blob, get_blob_client, upload_blob
from docingest.db.mongodb import (
    delete_document,
    find_by_hash,
    get_db,
    get_document,
    increment_version,
    insert_document,
    list_documents,
    update_document_status,
)
from docingest.db.qdrant import delete_doc_chunks, get_qdrant
from docingest.db.redis import get_redis_pool
from docingest.models.document import ContentType, DocumentStatus, SourceType

router = APIRouter()
log = structlog.get_logger()

CONTENT_TYPE_MAP = {
    "application/pdf": ContentType.PDF,
    "text/html": ContentType.HTML,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ContentType.DOCX,
    "text/plain": ContentType.TXT,
    "text/markdown": ContentType.MD,
}

EXTENSION_MAP = {
    ".pdf": ContentType.PDF,
    ".html": ContentType.HTML,
    ".htm": ContentType.HTML,
    ".docx": ContentType.DOCX,
    ".txt": ContentType.TXT,
    ".md": ContentType.MD,
    ".markdown": ContentType.MD,
}


def _detect_content_type(filename: str, mime: str | None) -> ContentType:
    if mime and mime in CONTENT_TYPE_MAP:
        return CONTENT_TYPE_MAP[mime]
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]
    raise HTTPException(status_code=400, detail=f"Unsupported file type: {filename}")


# --- Request/Response models ---


class UrlIngestRequest(BaseModel):
    url: HttpUrl
    force: bool = False
    chunk_size: int | None = Field(None, ge=100, le=2000)
    chunk_overlap: int | None = Field(None, ge=0, le=50)
    chunking_strategy: str | None = None


class BatchUrlRequest(BaseModel):
    urls: list[HttpUrl]
    force: bool = False


class ReprocessRequest(BaseModel):
    force: bool = True


class DocumentResponse(BaseModel):
    id: str
    tenant_id: str
    source_type: str
    source_ref: str
    content_type: str
    status: str
    error: str | None = None
    error_type: str | None = None
    error_stage: str | None = None
    file_size_bytes: int = 0
    chunk_count: int
    version: int
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    page: int
    per_page: int


# --- Helpers ---


async def _enqueue_conversion(doc_id: str, tenant_id: str, trace_id: str) -> None:
    pool = await get_redis_pool()
    await pool.enqueue_job("convert_document", doc_id=doc_id, tenant_id=tenant_id, trace_id=trace_id, _queue_name="arq:queue:convert")


def _doc_to_response(doc: dict) -> DocumentResponse:
    return DocumentResponse(
        id=str(doc["_id"]),
        tenant_id=doc["tenant_id"],
        source_type=doc["source_type"],
        source_ref=doc["source_ref"],
        content_type=doc["content_type"],
        status=doc["status"],
        error=doc.get("error"),
        error_type=doc.get("error_type"),
        error_stage=doc.get("error_stage"),
        file_size_bytes=doc.get("file_size_bytes", 0),
        chunk_count=doc.get("chunk_count", 0),
        version=doc.get("version", 1),
        created_at=doc["created_at"].isoformat(),
        updated_at=doc["updated_at"].isoformat(),
    )


# --- Routes ---


@router.post("/documents", status_code=202)
async def upload_document(
    request: Request,
    tenant: Tenant,
    file: UploadFile = File(...),
    force: bool = Query(False),
    chunk_size: int | None = Query(None, ge=100, le=2000, description="Max tokens per chunk"),
    chunk_overlap: int | None = Query(None, ge=0, le=50, description="Overlap percentage"),
    chunking_strategy: str | None = Query(None, description="Chunking strategy: 'fixed'"),
):
    if chunking_strategy is not None and chunking_strategy != "fixed":
        raise HTTPException(status_code=400, detail=f"Unsupported chunking strategy: {chunking_strategy}")

    content_type = _detect_content_type(file.filename or "unknown", file.content_type)
    raw_bytes = await file.read()
    file_size = len(raw_bytes)
    source_hash = hashlib.sha256(raw_bytes).hexdigest()

    db = await get_db()

    if not force:
        existing = await find_by_hash(db, tenant["tenant_id"], source_hash)
        if existing:
            return {"id": str(existing["_id"]), "status": "duplicate", "existing": True}

    blob_client = get_blob_client()
    doc_id_placeholder = source_hash[:12]
    blob_path = f"raw/{doc_id_placeholder}.{content_type}"
    upload_blob(blob_client, tenant["tenant_id"], blob_path, raw_bytes)

    # Build per-upload chunking config
    chunking_config: dict = {}
    if chunk_size is not None:
        chunking_config["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        chunking_config["chunk_overlap"] = chunk_overlap
    if chunking_strategy is not None:
        chunking_config["strategy"] = chunking_strategy

    doc_fields: dict = {
        "tenant_id": tenant["tenant_id"],
        "source_hash": source_hash,
        "source_type": SourceType.UPLOAD,
        "source_ref": file.filename or "upload",
        "content_type": content_type,
        "blob_path": blob_path,
        "file_size_bytes": file_size,
        "status": DocumentStatus.PENDING,
        "chunk_count": 0,
        "version": 1,
    }
    if chunking_config:
        doc_fields["chunking_config"] = chunking_config

    doc_id = await insert_document(db, doc_fields)

    state = getattr(request, "state", None)
    trace_id = getattr(state, "trace_id", None) or uuid.uuid4().hex[:16]
    await _enqueue_conversion(doc_id, tenant["tenant_id"], trace_id)
    log.info("document uploaded", doc_id=doc_id, content_type=content_type, trace_id=trace_id)

    return {"id": doc_id, "status": "pending"}


@router.post("/documents/url", status_code=202)
async def ingest_from_url(request: Request, tenant: Tenant, body: UrlIngestRequest):
    if body.chunking_strategy is not None and body.chunking_strategy != "fixed":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported chunking strategy: {body.chunking_strategy}",
        )

    import httpx

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        resp = await client.get(str(body.url))
        resp.raise_for_status()

    raw_bytes = resp.content
    file_size = len(raw_bytes)
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    content_type_header = resp.headers.get("content-type", "")
    url_str = str(body.url)

    # Detect type from URL extension or content-type header
    mime = content_type_header.split(";")[0].strip()
    content_type = _detect_content_type(url_str.split("?")[0], mime)

    db = await get_db()

    if not body.force:
        existing = await find_by_hash(db, tenant["tenant_id"], source_hash)
        if existing:
            return {"id": str(existing["_id"]), "status": "duplicate", "existing": True}

    blob_client = get_blob_client()
    blob_path = f"raw/{source_hash[:12]}.{content_type}"
    upload_blob(blob_client, tenant["tenant_id"], blob_path, raw_bytes)

    # Build per-upload chunking config
    chunking_config: dict = {}
    if body.chunk_size is not None:
        chunking_config["chunk_size"] = body.chunk_size
    if body.chunk_overlap is not None:
        chunking_config["chunk_overlap"] = body.chunk_overlap
    if body.chunking_strategy is not None:
        chunking_config["strategy"] = body.chunking_strategy

    doc_fields: dict = {
        "tenant_id": tenant["tenant_id"],
        "source_hash": source_hash,
        "source_type": SourceType.URL,
        "source_ref": url_str,
        "content_type": content_type,
        "blob_path": blob_path,
        "file_size_bytes": file_size,
        "status": DocumentStatus.PENDING,
        "chunk_count": 0,
        "version": 1,
    }
    if chunking_config:
        doc_fields["chunking_config"] = chunking_config

    doc_id = await insert_document(db, doc_fields)

    state = getattr(request, "state", None)
    trace_id = getattr(state, "trace_id", None) or uuid.uuid4().hex[:16]
    await _enqueue_conversion(doc_id, tenant["tenant_id"], trace_id)
    log.info("url ingested", doc_id=doc_id, url=url_str, trace_id=trace_id)

    return {"id": doc_id, "status": "pending"}


@router.post("/documents/batch", status_code=202)
async def batch_ingest(request: Request, tenant: Tenant, body: BatchUrlRequest):
    results = []
    for url in body.urls:
        try:
            result = await ingest_from_url(
                request, tenant, UrlIngestRequest(url=url, force=body.force)
            )
            results.append({"url": str(url), **result})
        except Exception as e:
            results.append({"url": str(url), "status": "error", "error": str(e)})

    return {"results": results}


@router.get("/documents/{doc_id}")
async def get_document_detail(tenant: Tenant, doc_id: str):
    db = await get_db()
    doc = await get_document(db, doc_id, tenant["tenant_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@router.get("/documents")
async def list_documents_route(
    tenant: Tenant,
    status: str | None = Query(None),
    content_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
):
    db = await get_db()
    sort_order = -1 if order == "desc" else 1
    docs, total = await list_documents(
        db, tenant["tenant_id"], status, content_type, page, per_page, sort, sort_order
    )
    return DocumentListResponse(
        documents=[_doc_to_response(d) for d in docs],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.delete("/documents/{doc_id}")
async def delete_document_route(tenant: Tenant, doc_id: str):
    db = await get_db()
    doc = await get_document(db, doc_id, tenant["tenant_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete chunks from Qdrant
    qdrant = await get_qdrant()
    await delete_doc_chunks(qdrant, tenant["tenant_id"], doc_id)

    # Delete blobs
    blob_client = get_blob_client()
    if doc.get("blob_path"):
        try:
            delete_blob(blob_client, tenant["tenant_id"], doc["blob_path"])
        except Exception:
            pass
    if doc.get("markdown_blob_path"):
        try:
            delete_blob(blob_client, tenant["tenant_id"], doc["markdown_blob_path"])
        except Exception:
            pass

    await delete_document(db, doc_id, tenant["tenant_id"])
    log.info("document deleted", doc_id=doc_id)

    return {"id": doc_id, "status": "deleted"}


@router.post("/documents/{doc_id}/reprocess", status_code=202)
async def reprocess_document(request: Request, tenant: Tenant, doc_id: str):
    db = await get_db()
    doc = await get_document(db, doc_id, tenant["tenant_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete existing chunks (may not exist on first processing)
    try:
        qdrant = await get_qdrant()
        await delete_doc_chunks(qdrant, tenant["tenant_id"], doc_id)
    except Exception:
        pass

    # Increment version and reset status
    await increment_version(db, doc_id)
    state = getattr(request, "state", None)
    trace_id = getattr(state, "trace_id", None) or uuid.uuid4().hex[:16]
    await _enqueue_conversion(doc_id, tenant["tenant_id"], trace_id)
    log.info("document reprocessing", doc_id=doc_id, trace_id=trace_id)

    return {"id": doc_id, "status": "pending", "version": doc.get("version", 1) + 1}


@router.get("/documents/{doc_id}/markdown")
async def get_document_markdown(tenant: Tenant, doc_id: str):
    """Download the converted markdown for a document."""
    db = await get_db()
    doc = await get_document(db, doc_id, tenant["tenant_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc["status"] not in ("converted", "chunking", "complete"):
        raise HTTPException(status_code=400, detail="Document not yet converted")

    md_blob_path = doc.get("markdown_blob_path")
    if not md_blob_path:
        raise HTTPException(status_code=404, detail="Markdown file not found")

    blob_client = get_blob_client()
    try:
        md_bytes = download_blob(blob_client, tenant["tenant_id"], md_blob_path)
    except Exception:
        raise HTTPException(status_code=404, detail="Markdown file not found in storage")

    return PlainTextResponse(md_bytes.decode("utf-8"), media_type="text/markdown")
