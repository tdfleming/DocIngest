"""ARQ worker: chunking + embedding.

Consumes 'chunk_and_embed' jobs from Redis. Downloads Markdown from MinIO,
runs the two-pass chunker, embeds chunks via FastEmbed, and upserts vectors
to Qdrant.
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime

import structlog
from qdrant_client.models import PointStruct

from docingest.logging_config import configure_logging

configure_logging()

from docingest.config import settings  # noqa: E402
from docingest.db.blob import download_blob, get_blob_client  # noqa: E402
from docingest.db.mongodb import get_db, get_document, update_document_status  # noqa: E402
from docingest.db.qdrant import (  # noqa: E402
    delete_doc_chunks,
    ensure_collection,
    get_qdrant,
    upsert_chunks,
)
from docingest.db.redis import get_redis_pool, get_redis_settings  # noqa: E402
from docingest.models.document import DocumentStatus  # noqa: E402
from docingest.services.app_logger import log_event  # noqa: E402
from docingest.services.chunking import chunk_document  # noqa: E402
from docingest.services.embedding import embed_texts  # noqa: E402

log = structlog.get_logger()


async def chunk_and_embed(ctx: dict, doc_id: str, tenant_id: str, trace_id: str = "") -> None:
    db = await get_db()
    blob_client = get_blob_client()
    qdrant = await get_qdrant()
    structlog.contextvars.bind_contextvars(trace_id=trace_id, doc_id=doc_id)

    try:
        await update_document_status(db, doc_id, DocumentStatus.CHUNKING)
        asyncio.create_task(
            log_event(
                "info", "chunking_start", "chunker",
                trace_id=trace_id, doc_id=doc_id, tenant_id=tenant_id,
            )
        )

        # Stage: fetch document record
        doc = await get_document(db, doc_id, tenant_id)
        if not doc:
            log.error("document not found", error_type="not_found")
            await update_document_status(
                db,
                doc_id,
                DocumentStatus.FAILED,
                extra_fields={
                    "error": "Document record not found in database",
                    "error_type": "not_found",
                    "error_stage": "chunking",
                },
            )
            return

        # Stage: download markdown
        try:
            t0 = time.monotonic()
            loop = asyncio.get_running_loop()
            markdown_bytes = await loop.run_in_executor(
                None, download_blob, blob_client, tenant_id, doc["markdown_blob_path"]
            )
            markdown = markdown_bytes.decode("utf-8")
            download_ms = round((time.monotonic() - t0) * 1000, 1)
        except Exception as e:
            log.error(
                "markdown download failed",
                error_type="download_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                DocumentStatus.FAILED,
                extra_fields={
                    "error": f"Failed to download markdown from storage: {e}",
                    "error_type": "download_error",
                    "error_stage": "chunking",
                },
            )
            return

        # Stage: chunk document
        try:
            t0 = time.monotonic()
            chunk_cfg = doc.get("chunking_config", {})
            chunks = chunk_document(
                markdown,
                max_tokens=chunk_cfg.get("chunk_size"),
                overlap_percent=chunk_cfg.get("chunk_overlap"),
            )
            chunk_ms = round((time.monotonic() - t0) * 1000, 1)
        except Exception as e:
            log.error(
                "chunking failed",
                error_type="chunking_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                DocumentStatus.FAILED,
                extra_fields={
                    "error": f"Failed to chunk document: {e}",
                    "error_type": "chunking_error",
                    "error_stage": "chunking",
                },
            )
            return

        if not chunks:
            log.warning("no chunks produced")
            await update_document_status(
                db, doc_id, DocumentStatus.COMPLETE, extra_fields={"chunk_count": 0}
            )
            return

        # Stage: embed texts
        try:
            t0 = time.monotonic()
            texts = [c["chunk_text"] for c in chunks]
            loop = asyncio.get_running_loop()
            vectors = await loop.run_in_executor(None, embed_texts, texts)
            embed_ms = round((time.monotonic() - t0) * 1000, 1)
        except Exception as e:
            log.error(
                "embedding failed",
                error_type="embedding_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                DocumentStatus.FAILED,
                extra_fields={
                    "error": f"Failed to generate embeddings: {e}",
                    "error_type": "embedding_error",
                    "error_stage": "chunking",
                },
            )
            return

        # Stage: upsert to Qdrant
        try:
            t0 = time.monotonic()
            await ensure_collection(qdrant, tenant_id)

            # Remove stale chunks from prior versions before upserting
            if doc.get("version", 1) > 1:
                await delete_doc_chunks(qdrant, tenant_id, doc_id)

            now = datetime.now(UTC).isoformat()

            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "doc_id": doc_id,
                        "doc_version": doc.get("version", 1),
                        "chunk_index": chunk["chunk_index"],
                        "chunk_text": chunk["chunk_text"],
                        "heading_chain": chunk["heading_chain"],
                        "source_ref": doc.get("source_ref", ""),
                        "content_type": doc.get("content_type", ""),
                        "char_offset": chunk["char_offset"],
                        "token_count": chunk["token_count"],
                        "created_at": now,
                    },
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]

            await upsert_chunks(qdrant, tenant_id, points)
            upsert_ms = round((time.monotonic() - t0) * 1000, 1)
        except Exception as e:
            log.error(
                "qdrant upsert failed",
                error_type="storage_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                DocumentStatus.FAILED,
                extra_fields={
                    "error": f"Failed to store vectors in Qdrant: {e}",
                    "error_type": "storage_error",
                    "error_stage": "chunking",
                },
            )
            return

        await update_document_status(
            db,
            doc_id,
            DocumentStatus.COMPLETE,
            extra_fields={
                "chunk_count": len(chunks),
                "processed_at": datetime.now(UTC),
            },
        )

        # Enqueue graph building if enabled
        if settings.graph_rag_enabled:
            pool = await get_redis_pool()
            await pool.enqueue_job(
                "build_graph",
                doc_id=doc_id,
                tenant_id=tenant_id,
                trace_id=trace_id,
                _queue_name="arq:queue:graph",
            )

        asyncio.create_task(
            log_event(
                "info", "chunking_complete", "chunker",
                trace_id=trace_id, doc_id=doc_id, tenant_id=tenant_id,
                details={
                    "chunks": len(chunks),
                    "download_ms": download_ms,
                    "chunk_ms": chunk_ms,
                    "embed_ms": embed_ms,
                    "upsert_ms": upsert_ms,
                },
            )
        )

        log.info(
            "chunking complete",
            chunks=len(chunks),
            download_ms=download_ms,
            chunk_ms=chunk_ms,
            embed_ms=embed_ms,
            upsert_ms=upsert_ms,
        )

    except Exception as e:
        log.error(
            "chunking failed unexpectedly",
            error_type="unknown_error",
            error=str(e),
        )
        asyncio.create_task(
            log_event(
                "error", "chunking_failed", "chunker",
                trace_id=trace_id, doc_id=doc_id, tenant_id=tenant_id,
                error=str(e),
            )
        )
        await update_document_status(
            db,
            doc_id,
            DocumentStatus.FAILED,
            extra_fields={
                "error": str(e),
                "error_type": "unknown_error",
                "error_stage": "chunking",
            },
        )
    finally:
        structlog.contextvars.unbind_contextvars("trace_id", "doc_id")


class WorkerSettings:
    functions = [chunk_and_embed]
    redis_settings = get_redis_settings()
    queue_name = "arq:queue:chunk"
    max_jobs = 8
    job_timeout = 300
    max_tries = 3
    retry_delay = 15
