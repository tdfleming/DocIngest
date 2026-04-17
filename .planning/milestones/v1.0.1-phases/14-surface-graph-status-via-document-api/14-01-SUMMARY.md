---
phase: 14-surface-graph-status-via-document-api
plan: 01
subsystem: document-api
tags: [graph-rag, document-response, api, testing]
requirements_completed: [GRAPH-WORKER-01, GRAPH-WORKER-04]
files_modified:
  created:
    - tests/test_documents_graph_response.py
  modified:
    - src/docingest/models/document.py
    - src/docingest/api/routes/documents.py
tasks_completed: 2
duration_minutes: 5
decisions:
  - "D-05 honored: 4 graph fields always present on DocumentResponse regardless of graph_rag_enabled"
  - "D-11 honored: graph_built_at serialized with .isoformat() conditional on doc.get() to handle legacy docs"
  - "D-07 honored: single _doc_to_response mapper serves both GET /v1/documents/{id} and GET /v1/documents list"
  - "Tests call _doc_to_response directly (not via HTTP TestClient) against real MongoDB data"
completed_date: "2026-04-17"
---

# Phase 14 Plan 01: Surface Graph Status via Document API Summary

**One-liner:** Added `graph_status`, `entity_count`, `relationship_count`, `graph_built_at` to `DocumentResponse` and `_doc_to_response`, closing gap INT-02 where the mapper stripped graph fields the worker already writes to MongoDB.

## What Shipped

### Model change (1 field)
- `src/docingest/models/document.py`: Added `graph_built_at: datetime | None = None` to `Document` model after `relationship_count` (D-09). Provides formal type safety for what the graph-worker already writes via `extra_fields`.

### API response change (4 fields + 4 mapper lines)
- `src/docingest/api/routes/documents.py`:
  - `DocumentResponse`: Added 4 fields after `chunk_count`, before `version`:
    - `graph_status: str | None = None`
    - `entity_count: int = 0`
    - `relationship_count: int = 0`
    - `graph_built_at: str | None = None` (ISO 8601 string, not datetime)
  - `_doc_to_response`: Added 4 keyword arguments populating the new fields from the raw MongoDB dict using `.get()` with defaults and `.isoformat()` for the timestamp (D-11).

### Tests (4 integration tests)
- `tests/test_documents_graph_response.py`: New test file with 4 passing integration tests against real MongoDB:
  1. `test_get_document_returns_graph_defaults` — non-built docs return None/0/None defaults
  2. `test_get_document_returns_graph_populated` — graph-built docs return actual values + ISO timestamp string
  3. `test_list_documents_returns_graph_fields` — list endpoint returns all 4 graph fields
  4. `test_graph_fields_present_when_graph_disabled` — fields always present on the model (no conditional logic)

## Decisions Honored

- **D-01**: All 4 fields exposed (not just 3) — `graph_built_at` included for UI timestamp UX.
- **D-02**: Types match spec — `str | None` on response, `datetime | None` on model, `int = 0` for counts.
- **D-03**: Defaults for non-graph-built docs: `graph_status=None`, counts=0, `graph_built_at=None`. `.get()` handles missing dict keys on legacy docs without `KeyError`.
- **D-05**: No conditional field omission — all 4 fields always present on `DocumentResponse`.
- **D-06**: Same response shape regardless of `settings.graph_rag_enabled`.
- **D-07**: Single `_doc_to_response` edit point — covers both GET detail (line 319) and GET list (line 338).
- **D-08**: Upload/reprocess/delete/batch-URL/URL-ingest routes NOT modified.
- **D-09**: `graph_built_at` added to `Document` model directly after `relationship_count`.
- **D-10**: `src/docingest/workers/graph_builder.py` NOT modified — write path unchanged.
- **D-11**: Serialization: `doc["graph_built_at"].isoformat() if doc.get("graph_built_at") else None` — mirrors `created_at`/`updated_at` pattern.

## Files NOT Modified

- `src/docingest/workers/graph_builder.py` — write path already correct (D-10)
- `src/docingest/db/mongodb.py` — `get_document`/`list_documents` already return full raw dicts
- `src/docingest/db/graph_store.py` — unrelated to this phase
- Frontend code — no consumer yet

## Requirements Closed

- **GRAPH-WORKER-01**: `DocumentResponse` now includes `graph_status`, `entity_count`, `relationship_count` — `GET /v1/documents/{id}` returns them (integration-tested).
- **GRAPH-WORKER-04**: `entity_count` and `relationship_count` exposed; non-null values returned when graph build completed (integration-tested via `test_get_document_returns_graph_populated`).
- **INT-02** (gap): `_doc_to_response` no longer strips graph fields.

## Deviations from Plan

None — plan executed exactly as written.

## Follow-up

- Phase 15: Code quality and hardening (asyncio deprecation fix in `entity_extraction.py`, remove duplicate `ensure_graph_indexes` call).

## Self-Check: PASSED

Files created/modified:
- FOUND: src/docingest/models/document.py (modified)
- FOUND: src/docingest/api/routes/documents.py (modified)
- FOUND: tests/test_documents_graph_response.py (created)

Commits:
- FOUND: 9b6cf11 (feat: surface 4 graph fields)
- FOUND: d51c199 (test: add integration tests)
