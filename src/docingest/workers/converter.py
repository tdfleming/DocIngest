"""ARQ worker: document conversion (Docling).

Consumes 'convert_document' jobs from Redis. Downloads raw file from MinIO,
converts to Markdown via Docling, uploads Markdown back to MinIO, and enqueues
the chunking job.
"""

import time

import structlog

from docingest.logging_config import configure_logging

configure_logging()

from docingest.db.blob import download_blob, get_blob_client, upload_blob
from docingest.db.mongodb import get_db, update_document_status
from docingest.db.redis import get_redis_pool, get_redis_settings
from docingest.models.document import DocumentStatus
from docingest.services.conversion import convert_to_markdown, extract_metadata

log = structlog.get_logger()


async def convert_document(ctx: dict, doc_id: str, tenant_id: str, trace_id: str = "") -> None:
    db = await get_db()
    blob_client = get_blob_client()
    structlog.contextvars.bind_contextvars(trace_id=trace_id, doc_id=doc_id)

    try:
        await update_document_status(db, doc_id, DocumentStatus.CONVERTING)

        # Stage: fetch document record
        from bson import ObjectId

        doc = await db.documents.find_one({"_id": ObjectId(doc_id)})
        if not doc:
            log.error("document not found", error_type="not_found")
            await update_document_status(
                db,
                doc_id,
                DocumentStatus.FAILED,
                extra_fields={
                    "error": "Document record not found in database",
                    "error_type": "not_found",
                    "error_stage": "converting",
                },
            )
            return

        # Stage: download raw file
        try:
            t0 = time.monotonic()
            raw_bytes = download_blob(blob_client, tenant_id, doc["blob_path"])
            download_ms = round((time.monotonic() - t0) * 1000, 1)
        except Exception as e:
            log.error(
                "download failed",
                error_type="download_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                DocumentStatus.FAILED,
                extra_fields={
                    "error": f"Failed to download source file from storage: {e}",
                    "error_type": "download_error",
                    "error_stage": "converting",
                },
            )
            return

        # Stage: convert to markdown
        try:
            t0 = time.monotonic()
            markdown = convert_to_markdown(raw_bytes, doc["content_type"], doc["source_ref"])
            convert_ms = round((time.monotonic() - t0) * 1000, 1)
        except Exception as e:
            log.error(
                "conversion to markdown failed",
                error_type="conversion_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                DocumentStatus.FAILED,
                extra_fields={
                    "error": f"Failed to convert {doc['content_type']} to markdown: {e}",
                    "error_type": "conversion_error",
                    "error_stage": "converting",
                },
            )
            return

        # Stage: upload markdown
        md_blob_path = f"markdown/{doc_id}.md"
        try:
            t0 = time.monotonic()
            upload_blob(
                blob_client, tenant_id, md_blob_path, markdown.encode("utf-8"), "text/markdown"
            )
            upload_ms = round((time.monotonic() - t0) * 1000, 1)
        except Exception as e:
            log.error(
                "markdown upload failed",
                error_type="upload_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                DocumentStatus.FAILED,
                extra_fields={
                    "error": f"Failed to upload converted markdown to storage: {e}",
                    "error_type": "upload_error",
                    "error_stage": "converting",
                },
            )
            return

        # Extract metadata
        meta = extract_metadata(markdown)

        await update_document_status(
            db,
            doc_id,
            DocumentStatus.CONVERTED,
            extra_fields={
                "markdown_blob_path": md_blob_path,
                "metadata.title": meta.get("title"),
                "metadata.word_count": meta.get("word_count", 0),
            },
        )

        # Enqueue chunking job
        pool = await get_redis_pool()
        await pool.enqueue_job("chunk_and_embed", doc_id=doc_id, tenant_id=tenant_id, trace_id=trace_id, _queue_name="arq:queue:chunk")

        log.info(
            "conversion complete",
            word_count=meta.get("word_count"),
            download_ms=download_ms,
            convert_ms=convert_ms,
            upload_ms=upload_ms,
        )

    except Exception as e:
        log.error(
            "conversion failed",
            error_type="unknown_error",
            error=str(e),
        )
        await update_document_status(
            db,
            doc_id,
            DocumentStatus.FAILED,
            extra_fields={
                "error": str(e),
                "error_type": "unknown_error",
                "error_stage": "converting",
            },
        )
    finally:
        structlog.contextvars.unbind_contextvars("trace_id", "doc_id")


class WorkerSettings:
    functions = [convert_document]
    redis_settings = get_redis_settings()
    queue_name = "arq:queue:convert"
    max_jobs = 4
    job_timeout = 600  # 10 min — Docling can be slow on large PDFs
    max_tries = 3
    retry_delay = 30
