"""ARQ worker: chunking + embedding.

Consumes 'chunk_document' jobs from Redis. Downloads Markdown from MinIO,
runs the two-pass chunker, embeds chunks via FastEmbed, and upserts vectors
to Qdrant.
"""

import uuid
from datetime import datetime

import structlog
from qdrant_client.models import PointStruct

from docingest.db.blob import download_blob, get_blob_client
from docingest.db.mongodb import get_db, get_document, update_document_status
from docingest.db.qdrant import ensure_collection, get_qdrant, upsert_chunks
from docingest.db.redis import get_redis_settings
from docingest.models.document import DocumentStatus
from docingest.services.chunking import chunk_document
from docingest.services.embedding import embed_texts

log = structlog.get_logger()


async def chunk_and_embed(ctx: dict, doc_id: str, tenant_id: str) -> None:
    db = await get_db()
    blob_client = get_blob_client()
    qdrant = await get_qdrant()

    try:
        await update_document_status(db, doc_id, DocumentStatus.CHUNKING)

        # Stage: fetch document record
        doc = await get_document(db, doc_id, tenant_id)
        if not doc:
            log.error("document not found", doc_id=doc_id, error_type="not_found")
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
            markdown_bytes = download_blob(blob_client, tenant_id, doc["markdown_blob_path"])
            markdown = markdown_bytes.decode("utf-8")
        except Exception as e:
            log.error(
                "markdown download failed",
                doc_id=doc_id,
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
            chunk_cfg = doc.get("chunking_config", {})
            chunks = chunk_document(
                markdown,
                max_tokens=chunk_cfg.get("chunk_size"),
                overlap_percent=chunk_cfg.get("chunk_overlap"),
            )
        except Exception as e:
            log.error(
                "chunking failed",
                doc_id=doc_id,
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
            log.warning("no chunks produced", doc_id=doc_id)
            await update_document_status(
                db, doc_id, DocumentStatus.COMPLETE, extra_fields={"chunk_count": 0}
            )
            return

        # Stage: embed texts
        try:
            texts = [c["chunk_text"] for c in chunks]
            vectors = embed_texts(texts)
        except Exception as e:
            log.error(
                "embedding failed",
                doc_id=doc_id,
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
            await ensure_collection(qdrant, tenant_id)
            now = datetime.utcnow().isoformat()

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
                for chunk, vector in zip(chunks, vectors)
            ]

            await upsert_chunks(qdrant, tenant_id, points)
        except Exception as e:
            log.error(
                "qdrant upsert failed",
                doc_id=doc_id,
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
                "processed_at": datetime.utcnow(),
            },
        )

        log.info("chunking complete", doc_id=doc_id, chunks=len(chunks))

    except Exception as e:
        log.error(
            "chunking failed unexpectedly",
            doc_id=doc_id,
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
                "error_stage": "chunking",
            },
        )


class WorkerSettings:
    functions = [chunk_and_embed]
    redis_settings = get_redis_settings()
    max_jobs = 8
    job_timeout = 300
    max_tries = 3
    retry_delay = 15
