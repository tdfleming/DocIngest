---
phase: 10-graph-builder-worker
plan: 01
subsystem: graph-pipeline
tags: [arq-worker, graph-rag, entity-extraction, knowledge-graph, qdrant, mongodb]
dependency_graph:
  requires: [08-graph-data-models, 09-entity-extraction]
  provides: [graph-builder-worker, qdrant-scroll-helper, graph-status-tracking]
  affects: [chunker-worker, document-model, docker-compose]
tech_stack:
  added: []
  patterns: [arq-worker-staged-error-handling, qdrant-cursor-scroll, batch-entity-resolution]
key_files:
  created:
    - src/docingest/workers/graph_builder.py
    - docker/graph-worker.Dockerfile
  modified:
    - src/docingest/workers/chunker.py
    - src/docingest/db/qdrant.py
    - src/docingest/models/document.py
    - docker-compose.yml
    - .env.example
decisions:
  - "graph_status is a plain str|None field, not a DocumentStatus enum value, to avoid breaking existing frontend/API"
  - "Batch entity resolution: single find_entities_by_names call for all unique names across all chunks, then resolve locally"
  - "1 replica for graph-worker (not 2) because spaCy model uses ~500MB RAM per process"
  - "graph-worker does not depend on minio since it reads from Qdrant and writes to MongoDB only"
metrics:
  duration: 4min
  completed: "2026-04-12T23:39:26Z"
  tasks: 3
  files: 7
---

# Phase 10 Plan 01: Graph Builder Worker Summary

Graph builder ARQ worker that extracts entities/relationships from document chunks via spaCy NLP and persists knowledge graph to MongoDB, completing the Graph RAG pipeline from upload through graph construction.

## What Was Built

### Task 1: Document model fields, Qdrant scroll helper, env config (0368201)
- Added `graph_status` (str|None), `entity_count` (int), `relationship_count` (int) fields to Document model after `chunk_count`
- Added `get_doc_chunks()` to `qdrant.py` using cursor-based scroll pagination with `scroll_filter` (not `query_filter`), `with_vectors=False`, 100-point batches
- Appended `GRAPH_RAG_ENABLED=false` and `SPACY_MODEL=en_core_web_lg` to `.env.example`

### Task 2: Graph builder worker and chunker enqueue wiring (8c451b1)
- Created `src/docingest/workers/graph_builder.py` following exact ARQ worker pattern:
  - `configure_logging()` first, then all imports with `# noqa: E402`
  - 7-stage `build_graph` job: validate doc, fetch chunks, clear stale data, extract entities/relationships, batch resolve + upsert entities, upsert relationships, update document
  - Belt-and-suspenders `graph_rag_enabled` check at worker entry
  - Re-processing detection: clears stale graph via `delete_doc_graph_data` when `version > 1` or `graph_status is not None`
  - Batch entity resolution: collects all entity names from all chunks, single `find_entities_by_names` call, then `resolve_entity` locally per unique (name, type) pair
  - Entity lookup dict keyed by lowercase name for relationship wiring
  - Outer catch-all sets `graph_status="failed"` with error details
  - WorkerSettings: queue `arq:queue:graph`, max_jobs=4, job_timeout=600, max_tries=2, retry_delay=30
- Modified `chunker.py`: added `settings` and `get_redis_pool` imports, added conditional `enqueue_job("build_graph")` block between COMPLETE status update and log_event call

### Task 3: Dockerfile and docker-compose service (79f7270)
- Created `docker/graph-worker.Dockerfile` based on chunker pattern with `pip install spacy && python -m spacy download en_core_web_lg`
- Added `graph-worker` service to `docker-compose.yml` with 1 replica, depends on mongodb/redis/qdrant (no minio), `restart: unless-stopped`

## Decisions Made

1. **graph_status as plain string, not enum** -- Keeps Document status field unchanged (still `DocumentStatus.COMPLETE` after chunking). `graph_status` is an independent tracking field with values None/"building"/"complete"/"failed". This avoids breaking the existing frontend/API status display.

2. **Batch entity resolution** -- Instead of N MongoDB queries (one per chunk), all unique entity names are collected first, then a single `find_entities_by_names` batch lookup is performed, followed by local `resolve_entity` calls. This prevents query count explosion for large documents.

3. **1 replica for graph-worker** -- spaCy `en_core_web_lg` model uses ~500MB RAM per process. Starting conservative with 1 replica; can scale later.

4. **No minio dependency** -- graph-worker reads chunk text from Qdrant payloads and writes entities/relationships to MongoDB. No blob storage interaction needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed import ordering in chunker.py**
- **Found during:** Task 2
- **Issue:** Adding `settings` and `get_redis_pool` imports caused ruff I001 (unsorted import block) because `docingest.config` sorts before `docingest.db`
- **Fix:** Ran `ruff check --fix` to auto-sort imports
- **Files modified:** src/docingest/workers/chunker.py
- **Commit:** 8c451b1

## Verification Results

All 6 verification checks passed:
1. Worker module imports without errors
2. Qdrant scroll helper importable
3. Document model has new fields with correct defaults
4. All modified files pass ruff linting
5. Chunker has graph_rag_enabled feature flag gate
6. Docker config complete (Dockerfile + compose service)

## Known Stubs

None -- all functionality is fully wired. The graph builder calls real entity extraction functions from Phase 9 and real graph store CRUD from Phase 8.

## Self-Check: PASSED
