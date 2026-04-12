"""ARQ worker: knowledge graph construction.

Consumes 'build_graph' jobs from Redis. Fetches chunk payloads from Qdrant,
extracts entities and relationships via spaCy NLP, and upserts them to the
MongoDB graph store.
"""

import asyncio
import time
from datetime import UTC, datetime

import structlog

from docingest.logging_config import configure_logging

configure_logging()

from docingest.config import settings  # noqa: E402
from docingest.db.graph_store import (  # noqa: E402
    delete_doc_graph_data,
    find_entities_by_names,
    upsert_entity,
    upsert_relationship,
)
from docingest.db.mongodb import get_db, get_document, update_document_status  # noqa: E402
from docingest.db.qdrant import get_doc_chunks, get_qdrant  # noqa: E402
from docingest.db.redis import get_redis_settings  # noqa: E402
from docingest.models.document import DocumentStatus  # noqa: E402
from docingest.services.app_logger import log_event  # noqa: E402
from docingest.services.entity_extraction import (  # noqa: E402
    extract_entities_async,
    extract_relationships_async,
    resolve_entity,
)

log = structlog.get_logger()


async def build_graph(ctx: dict, doc_id: str, tenant_id: str, trace_id: str = "") -> None:
    db = await get_db()
    qdrant = await get_qdrant()
    structlog.contextvars.bind_contextvars(trace_id=trace_id, doc_id=doc_id)
    t_start = time.monotonic()

    try:
        # Stage 1: Fetch document and validate
        if not settings.graph_rag_enabled:
            log.warning("graph_rag_enabled is false, skipping graph build")
            return

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
                    "error_stage": "graph_building",
                },
            )
            return

        if doc["status"] != DocumentStatus.COMPLETE:
            log.warning(
                "document not in COMPLETE status, skipping graph build",
                status=doc["status"],
            )
            return

        await update_document_status(
            db,
            doc_id,
            doc["status"],
            extra_fields={"graph_status": "building"},
        )

        # Stage 2: Fetch chunks from Qdrant
        try:
            chunks = await get_doc_chunks(qdrant, tenant_id, doc_id)
        except Exception as e:
            log.error(
                "failed to fetch chunks from Qdrant",
                error_type="qdrant_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                doc["status"],
                extra_fields={
                    "graph_status": "failed",
                    "error": f"Failed to fetch chunks from Qdrant: {e}",
                    "error_type": "qdrant_error",
                    "error_stage": "graph_building",
                },
            )
            return

        if not chunks:
            log.info("no chunks found, marking graph complete with zero counts")
            await update_document_status(
                db,
                doc_id,
                doc["status"],
                extra_fields={
                    "graph_status": "complete",
                    "entity_count": 0,
                    "relationship_count": 0,
                },
            )
            return

        log.info("fetched chunks for graph building", chunk_count=len(chunks))

        # Stage 3: Clear stale graph data (re-processing)
        if doc.get("version", 1) > 1 or doc.get("graph_status") is not None:
            log.info("clearing stale graph data before rebuild")
            await delete_doc_graph_data(db, tenant_id, doc_id)

        # Stage 4: Extract entities and relationships from ALL chunks
        all_extracted_entities: list[dict] = []
        all_extracted_relationships: list[dict] = []

        for chunk in chunks:
            text = chunk.payload["chunk_text"]
            chunk_id = str(chunk.id)

            try:
                entities = await extract_entities_async(text)
                relationships = await extract_relationships_async(text, entities)
            except Exception as e:
                log.warning(
                    "entity extraction failed for chunk, skipping",
                    chunk_id=chunk_id,
                    error=str(e),
                )
                continue

            for ent in entities:
                all_extracted_entities.append({
                    "name": ent["name"],
                    "entity_type": ent["entity_type"],
                    "chunk_id": chunk_id,
                })

            for rel in relationships:
                all_extracted_relationships.append({
                    "source": rel["source"],
                    "target": rel["target"],
                    "relation_type": rel["relation_type"],
                    "description": rel["description"],
                    "chunk_id": chunk_id,
                })

        # Stage 5: Batch entity resolution and upsert
        try:
            unique_names = list({e["name"] for e in all_extracted_entities})
            existing = await find_entities_by_names(db, tenant_id, unique_names)

            # Build (name, entity_type) -> list[chunk_ids] mapping
            entity_chunks: dict[tuple[str, str], list[str]] = {}
            for ent in all_extracted_entities:
                key = (ent["name"], str(ent["entity_type"]))
                entity_chunks.setdefault(key, []).append(ent["chunk_id"])

            # Resolve and upsert each unique entity
            entity_lookup: dict[str, str] = {}  # lowercase name -> entity_id
            entity_count = 0

            for (name, entity_type), chunk_ids in entity_chunks.items():
                resolved_name = resolve_entity(name, entity_type, existing) or name
                entity_id = await upsert_entity(
                    db,
                    tenant_id,
                    resolved_name,
                    entity_type,
                    doc_id,
                    list(set(chunk_ids)),
                )
                entity_lookup[name.lower()] = entity_id
                entity_count += 1

        except Exception as e:
            log.error(
                "entity resolution/upsert failed",
                error_type="graph_entity_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                doc["status"],
                extra_fields={
                    "graph_status": "failed",
                    "error": f"Entity resolution/upsert failed: {e}",
                    "error_type": "graph_entity_error",
                    "error_stage": "graph_building",
                },
            )
            return

        # Stage 6: Upsert relationships
        try:
            relationship_count = 0
            for rel in all_extracted_relationships:
                source_id = entity_lookup.get(rel["source"].lower())
                target_id = entity_lookup.get(rel["target"].lower())
                if not source_id or not target_id:
                    continue
                await upsert_relationship(
                    db,
                    tenant_id,
                    source_id,
                    target_id,
                    rel["relation_type"],
                    rel["description"],
                    doc_id,
                    [rel["chunk_id"]],
                )
                relationship_count += 1

        except Exception as e:
            log.error(
                "relationship upsert failed",
                error_type="graph_relationship_error",
                error=str(e),
            )
            await update_document_status(
                db,
                doc_id,
                doc["status"],
                extra_fields={
                    "graph_status": "failed",
                    "error": f"Relationship upsert failed: {e}",
                    "error_type": "graph_relationship_error",
                    "error_stage": "graph_building",
                },
            )
            return

        # Stage 7: Update document with completion
        elapsed_ms = round((time.monotonic() - t_start) * 1000, 1)
        await update_document_status(
            db,
            doc_id,
            DocumentStatus.COMPLETE,
            extra_fields={
                "graph_status": "complete",
                "entity_count": entity_count,
                "relationship_count": relationship_count,
                "graph_built_at": datetime.now(UTC),
            },
        )

        asyncio.create_task(
            log_event(
                "info",
                "graph_build_complete",
                "graph_builder",
                trace_id=trace_id,
                doc_id=doc_id,
                tenant_id=tenant_id,
                details={
                    "entity_count": entity_count,
                    "relationship_count": relationship_count,
                    "chunks_processed": len(chunks),
                    "elapsed_ms": elapsed_ms,
                },
            )
        )

        log.info(
            "graph build complete",
            entity_count=entity_count,
            relationship_count=relationship_count,
            chunks_processed=len(chunks),
            elapsed_ms=elapsed_ms,
        )

    except Exception as e:
        log.error(
            "graph building failed unexpectedly",
            error_type="unknown_error",
            error=str(e),
        )
        asyncio.create_task(
            log_event(
                "error",
                "graph_build_failed",
                "graph_builder",
                trace_id=trace_id,
                doc_id=doc_id,
                tenant_id=tenant_id,
                error=str(e),
            )
        )
        await update_document_status(
            db,
            doc_id,
            DocumentStatus.COMPLETE,
            extra_fields={
                "graph_status": "failed",
                "error": str(e),
                "error_type": "unknown_error",
                "error_stage": "graph_building",
            },
        )
    finally:
        structlog.contextvars.unbind_contextvars("trace_id", "doc_id")


class WorkerSettings:
    functions = [build_graph]
    redis_settings = get_redis_settings()
    queue_name = "arq:queue:graph"
    max_jobs = 4
    job_timeout = 600
    max_tries = 2
    retry_delay = 30
