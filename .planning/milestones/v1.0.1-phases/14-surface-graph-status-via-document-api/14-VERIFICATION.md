---
phase: 14-surface-graph-status-via-document-api
verified: 2026-04-16T00:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 14: Surface Graph Status via Document API — Verification Report

**Phase Goal:** Graph processing fields written by the worker must be visible on `GET /v1/documents/{id}` and list responses.
**Verified:** 2026-04-16
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | GET /v1/documents/{id} returns graph_status, entity_count, relationship_count, graph_built_at fields | VERIFIED | `documents.py` lines 93-96: all 4 fields on DocumentResponse; line 327 routes through `_doc_to_response` |
| 2  | GET /v1/documents list returns the 4 graph fields on each document | VERIFIED | `documents.py` line 346: `[_doc_to_response(d) for d in docs]`; both endpoints share the same mapper |
| 3  | Non-graph-built docs return graph_status=null, entity_count=0, relationship_count=0, graph_built_at=null | VERIFIED | `_doc_to_response` lines 136-139 use `.get()` with defaults; `test_get_document_returns_graph_defaults` PASSES |
| 4  | Graph-built docs return actual values (graph_status='complete', real counts, ISO timestamp) | VERIFIED | `test_get_document_returns_graph_populated` PASSES — asserts `entity_count==5`, `relationship_count==3`, `graph_built_at` is ISO string |
| 5  | Response shape is identical when settings.graph_rag_enabled=false (fields always present with defaults) | VERIFIED | `_doc_to_response` has no conditional on `graph_rag_enabled`; `test_graph_fields_present_when_graph_disabled` PASSES |
| 6  | Document model declares graph_built_at: datetime | None = None | VERIFIED | `document.py` line 58: `graph_built_at: datetime \| None = None` |
| 7  | Integration tests verify all of the above | VERIFIED | `tests/test_documents_graph_response.py` — 4 tests, all PASS in 2.16s |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/docingest/models/document.py` | graph_built_at field on Document model | VERIFIED | Line 58: `graph_built_at: datetime \| None = None` — correct type, correct default, correct position (after `relationship_count`) |
| `src/docingest/api/routes/documents.py` | 4 graph fields on DocumentResponse + _doc_to_response mapping | VERIFIED | Lines 93-96: DocumentResponse fields; lines 136-139: _doc_to_response kwargs — 8 total matches on grep |
| `tests/test_documents_graph_response.py` | Integration tests for graph fields in document API responses | VERIFIED | 143 lines, 4 test functions, all assertions substantive — no stubs |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `documents.py::DocumentResponse` | `models/document.py::Document` | Both declare graph_status, entity_count, relationship_count; DocumentResponse adds graph_built_at as str (ISO) while Document stores as datetime | WIRED | Lines 93-96 match exactly; type conversion at line 139 mirrors created_at/updated_at pattern |
| `documents.py::_doc_to_response` | MongoDB raw document dict | `doc.get("graph_status")` and siblings | WIRED | Lines 136-139 use `.get()` with correct defaults; `doc.get("graph_built_at")` guards against missing key on legacy docs |
| `workers/graph_builder.py` | `models/document.py::Document.graph_built_at` | Worker writes graph_built_at via extra_fields; model declaration provides type safety | WIRED (no change needed) | `git diff src/docingest/workers/graph_builder.py` is empty — write path unchanged, model now has formal type |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `documents.py::_doc_to_response` | `doc["graph_built_at"]`, `doc.get("entity_count", 0)`, etc. | MongoDB raw dict from `get_document` / `list_documents` | Yes — `get_document` returns full raw dict; worker writes real values via `update_document_status(extra_fields=...)` | FLOWING |
| `tests/test_documents_graph_response.py` | `seed_doc_with_graph` fixture | `insert_document(db, doc_fields)` with explicit graph field values | Yes — inserts `entity_count=5`, `relationship_count=3`, `graph_built_at=datetime.now(UTC)` then reads back via `get_document` | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| DocumentResponse and _doc_to_response importable | `python -c "from docingest.api.routes.documents import DocumentResponse, _doc_to_response; print('import OK')"` | `import OK` | PASS |
| 4 integration tests pass against real MongoDB | `pytest tests/test_documents_graph_response.py -x -v` | `4 passed in 2.16s` | PASS |
| Full test suite (66 tests) — no regressions | `pytest --ignore=tests/test_entity_extraction.py -v` | `66 passed in 6.07s` | PASS |
| Linter clean on all modified/created files | `ruff check src/docingest/models/document.py src/docingest/api/routes/documents.py tests/test_documents_graph_response.py` | `All checks passed!` | PASS |
| graph_builder.py and mongodb.py untouched | `git diff src/docingest/workers/graph_builder.py && git diff src/docingest/db/mongodb.py` | empty (no output) | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| GRAPH-WORKER-01 | 14-01-PLAN.md | DocumentResponse includes graph_status, entity_count, relationship_count; GET /v1/documents/{id} returns them | SATISFIED | documents.py lines 93-95; test_get_document_returns_graph_defaults + test_get_document_returns_graph_populated both PASS |
| GRAPH-WORKER-04 | 14-01-PLAN.md | entity_count and relationship_count surfaced via API; non-null when graph build completed | SATISFIED | documents.py lines 94-95; test_get_document_returns_graph_populated asserts entity_count==5, relationship_count==3 |

---

### Anti-Patterns Found

No anti-patterns found. Scanning for stubs, TODOs, hardcoded empty returns, and disconnected props produced no matches on modified files.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

---

### Human Verification Required

None. All 7 must-haves are programmatically verifiable and have been verified. The phase does not introduce UI components or external service integrations requiring manual testing.

---

### Gaps Summary

No gaps. All must-haves pass at all four verification levels (exists, substantive, wired, data flowing). The phase goal — "Graph processing fields written by the worker must be visible on GET /v1/documents/{id} and list responses" — is fully achieved.

**Grep-verifiable acceptance criteria audit:**

- `grep -nE 'graph_status|entity_count|relationship_count|graph_built_at' src/docingest/api/routes/documents.py` — **8 matches** (requirement: >= 8). PASS.
- `grep -n 'graph_built_at' src/docingest/models/document.py` — **1 match** at line 58. PASS.
- `git diff src/docingest/workers/graph_builder.py` — **empty**. PASS.
- `git diff src/docingest/db/mongodb.py` — **empty**. PASS.
- `tests/test_documents_graph_response.py` exists with **4 passing tests**. PASS.
- `ruff check src/` — **All checks passed!** PASS.

---

_Verified: 2026-04-16_
_Verifier: Claude (gsd-verifier)_
