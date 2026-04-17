# Phase 12: Restore Graph RAG Traceability — Research

**Researched:** 2026-04-16
**Domain:** Planning-artifact hygiene (REQUIREMENTS.md, MILESTONES.md, PROJECT.md, SUMMARY frontmatter)
**Confidence:** HIGH — all source code files read directly; no external lookups required

## RESEARCH COMPLETE

**Phase:** 12 — Restore Graph RAG Traceability
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**PROJECT.md updates:**
- Remove from Out of Scope: `Graph RAG / knowledge graph — research-grade complexity for marginal gains`
- Add to Validated requirements section: Graph RAG extension capabilities (entity extraction, graph data models, graph builder worker, community detection rebuild API) — each marked as `v1.0 extension`
- Update Context block: add sentence noting v1.0 was extended with Graph RAG (phases 8-11, 2026-04-12), reference `.planning/v1.0-MILESTONE-AUDIT.md`
- Do NOT add a Constraint or Key Decision row for Graph RAG
- Bump `Last updated` to `2026-04-16 after v1.0 gap closure planning`

**MILESTONES.md updates:**
- Add new block under `v1.0 MVP (Shipped: 2026-03-04)` titled `### v1.0 Graph RAG Extension (2026-04-12)`
- Include: phases 8-11, delivered capabilities, stats (4 phases, 7 plans, 25 REQ-IDs), cross-reference to `.planning/v1.0-MILESTONE-AUDIT.md`
- Status: `⚠ Gap closure in flight (phases 12-15)`
- Do NOT create a new top-level `## v1.1` heading

**REQUIREMENTS.md expansion (schema):**
Every REQ-ID entry MUST include: Label, Description, Phase, Definition of Done (bulleted), Verification criteria (grep-able/test-runnable), Status

**Status overrides:**
- GRAPH-WORKER-02 → `Satisfied* (traceability added, VERIFICATION.md pending)`
- GRAPH-WORKER-05 → `Satisfied* (traceability added, VERIFICATION.md pending)`
- COMM-05 → `Satisfied* (traceability added, VERIFICATION.md pending)`
- All other REQ-IDs: leave status unchanged

**SUMMARY frontmatter additions:**
| SUMMARY file | `requirements-completed:` value |
|---|---|
| `.planning/phases/10-graph-builder-worker/10-01-SUMMARY.md` | `[GRAPH-WORKER-01, GRAPH-WORKER-02, GRAPH-WORKER-03, GRAPH-WORKER-04, GRAPH-WORKER-05]` |
| `.planning/phases/11-community-detection/11-01-SUMMARY.md` | `[COMM-01, COMM-02, COMM-03, COMM-04]` |
| `.planning/phases/11-community-detection/11-02-SUMMARY.md` | `[COMM-05]` |

**Commit strategy:**
1. `docs(12): add traceability CONTEXT` (already done)
2. `docs(12-01): expand REQUIREMENTS.md with full Graph RAG extension schema`
3. `docs(12-02): update PROJECT.md to reflect shipped Graph RAG extension`
4. `docs(12-03): update MILESTONES.md with v1.0 Graph RAG extension record`
5. `docs(12-04): add requirements-completed frontmatter to 10-01, 11-01, 11-02 SUMMARYs`
6. `docs(12-05): mark GRAPH-WORKER-02, GRAPH-WORKER-05, COMM-05 as satisfied in REQUIREMENTS.md` (may fold into 12-01)

**Ordering constraints:**
- REQUIREMENTS.md expansion (12-01) must land before status overrides (12-05)
- SUMMARY frontmatter edits (12-04) are independent — parallel with others
- PROJECT.md (12-02) and MILESTONES.md (12-03) are independent of everything else

### Claude's Discretion

- Whether to split `docs(12-01)` and `docs(12-05)` into separate commits — planner's call (single commit is fine, same file)
- Exact wording of prose description / DoD / verification-criteria per REQ-ID (must be grep-able and concrete)
- Internal ordering of REQ-IDs within REQUIREMENTS.md (keep existing phase grouping)

### Deferred Ideas (OUT OF SCOPE)

- Creating VERIFICATION.md for phases 8-11 — owned by `/gsd:verify-work`
- Creating VALIDATION.md for any phase — owned by `/gsd:validate-phase`
- Phase 08 tech debt (duplicate `ensure_graph_indexes` call) — phase 15
- Retroactive split into v1.1 / v2.0 milestones — explicitly rejected
- PROJECT.md Key Decisions table entries for Graph RAG architecture choices
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GRAPH-WORKER-02 | Worker fetches chunks via `get_doc_chunks` | Code confirmed: `get_doc_chunks` exported from `qdrant.py:110`, imported and called in `graph_builder.py:26,82` — wired, traceability record only needed |
| GRAPH-WORKER-05 | `graph-worker` Docker service + spaCy model download | Code confirmed: `docker/graph-worker.Dockerfile` exists with `python -m spacy download en_core_web_lg`, service wired in `docker-compose.yml` — traceability record only needed |
| COMM-05 | `POST /v1/graph/communities/rebuild` API route | Code confirmed: `src/docingest/api/routes/graph.py` has `rebuild_communities` at `POST /communities/rebuild`, mounted in `app.py:65` under `/v1` prefix — traceability record only needed |
</phase_requirements>

---

## Summary

Phase 12 is a pure documentation phase. All source code implementing the 25 Graph RAG extension REQ-IDs was shipped in phases 8-11. The gap is entirely in planning-artifact coverage: REQUIREMENTS.md has skeleton entries without descriptions/DoD/verification criteria; PROJECT.md still marks Graph RAG as out-of-scope; MILESTONES.md omits phases 8-11; three SUMMARY files (10-01, 11-01, 11-02) have no `requirements-completed` frontmatter.

**Primary recommendation:** Write REQUIREMENTS.md entries directly from the source-code read performed in this research document. Every DoD item and verification criterion below was confirmed by reading the actual shipped file — no inference required.

The three "orphaned" REQ-IDs (GRAPH-WORKER-02, GRAPH-WORKER-05, COMM-05) are fully wired in code. Flipping them to `Satisfied*` is justified by direct code inspection; the only thing missing is formal traceability.

---

## REQ-ID Inventory

This section is the primary deliverable for the planner. Each row contains everything needed to write the REQUIREMENTS.md entry.

### Phase 08 — Graph Data Models

#### GRAPH-01 — Entity, Relationship, Community Pydantic models

**Code anchor:** `src/docingest/models/graph.py:1-65` (whole file)
**Shipped behavior:** Three Pydantic v2 BaseModel classes (`Entity`, `Relationship`, `Community`) follow the exact document.py pattern — `Field(alias="_id")`, `model_config = {"populate_by_name": True}`, `datetime` defaults via `lambda: datetime.now(UTC)`. All three classes importable from `docingest.models.graph`.

**Definition of Done:**
- `src/docingest/models/graph.py` exists and exports `Entity`, `Relationship`, `Community`
- Each model uses `Field(default="", alias="_id")` for its id field and `model_config = {"populate_by_name": True}`
- All three models have `created_at` and `updated_at` with `datetime.now(UTC)` defaults

**Verification criteria:**
- `python -c "from docingest.models.graph import Entity, Relationship, Community; print('OK')"` exits 0
- `grep -n 'class Entity\|class Relationship\|class Community' src/docingest/models/graph.py` returns 3 matches
- `grep -n 'populate_by_name' src/docingest/models/graph.py` returns 3 matches

**Status:** Satisfied* (no VERIFICATION.md)

---

#### GRAPH-02 — `EntityType` enum + core entity fields

**Code anchor:** `src/docingest/models/graph.py:7-15` (`EntityType` StrEnum) and `18-32` (`Entity` model)
**Shipped behavior:** `EntityType(StrEnum)` with exactly 8 values: person, organization, location, date, event, product, concept, other. `Entity` has `aliases`, `doc_ids`, `chunk_ids`, `mention_count`, `embedding`, `metadata` fields with correct defaults.

**Definition of Done:**
- `EntityType` has exactly 8 values (person, organization, location, date, event, product, concept, other)
- `Entity.aliases`, `Entity.doc_ids`, `Entity.chunk_ids` default to empty list via `Field(default_factory=list)`
- `Entity.mention_count` defaults to 0; `Entity.embedding` defaults to None

**Verification criteria:**
- `python -c "from docingest.models.graph import EntityType; assert len(EntityType) == 8; print('OK')"` exits 0
- `grep -n 'class EntityType' src/docingest/models/graph.py` returns 1 match
- `pytest tests/test_graph_models.py -x -q` passes

**Status:** Satisfied* (no VERIFICATION.md)

---

#### GRAPH-03 — Relationship model with relation_type taxonomy

**Code anchor:** `src/docingest/models/graph.py:35-48` (`Relationship` model)
**Shipped behavior:** `Relationship` model with `source_entity_id`, `target_entity_id`, `relation_type` (plain string), `description` (default ""), `weight` (default 1.0), `doc_ids` and `chunk_ids` list fields.

**Definition of Done:**
- `Relationship` model exported from `docingest.models.graph`
- `relation_type` is a plain `str` (not an enum) enabling open vocabulary
- `weight` defaults to 1.0; `doc_ids` and `chunk_ids` default to empty list

**Verification criteria:**
- `python -c "from docingest.models.graph import Relationship; r = Relationship(tenant_id='t', source_entity_id='a', target_entity_id='b', relation_type='acquired'); assert r.weight == 1.0; print('OK')"` exits 0
- `grep -n 'relation_type' src/docingest/models/graph.py` returns at least 1 match

**Status:** Satisfied* (no VERIFICATION.md)

---

#### GRAPH-04 — `graph_store.py` CRUD: upsert/get entities and relationships

**Code anchor:** `src/docingest/db/graph_store.py:49-158` (`upsert_entity`, `upsert_relationship`); `161-174` (`get_entity_by_id`, `find_entities_by_names`)
**Shipped behavior:** Atomic upsert for entities (filter: `tenant_id + name + entity_type`) using `$addToSet` for doc_ids/chunk_ids/aliases, `$inc` for mention_count, `$setOnInsert` for created_at. Relationship upsert filters on `tenant_id + source + target + relation_type`. Both return entity/relationship ID as string.

**Definition of Done:**
- `upsert_entity` and `upsert_relationship` exported from `docingest.db.graph_store`
- Both functions use `update_one(upsert=True)` with `$addToSet` merge semantics
- `get_entity_by_id` and `find_entities_by_names` exported and functional

**Verification criteria:**
- `python -c "from docingest.db.graph_store import upsert_entity, upsert_relationship, get_entity_by_id, find_entities_by_names; print('OK')"` exits 0
- `grep -n 'addToSet\|upsert=True' src/docingest/db/graph_store.py` returns multiple matches
- `pytest tests/test_graph_store.py -x -q` passes

**Status:** Satisfied* (no VERIFICATION.md)

---

#### GRAPH-05 — Unique compound indexes for entity/relationship dedup

**Code anchor:** `src/docingest/db/graph_store.py:16-46` (`ensure_graph_indexes`)
**Shipped behavior:** `ensure_graph_indexes` creates: entities unique compound index `(tenant_id, name, entity_type)`; relationships unique compound index `(tenant_id, source_entity_id, target_entity_id, relation_type)`; communities unique index `(tenant_id, level, title)`. Also creates lookup indexes on doc_ids, entity_type, source/target IDs.

**Definition of Done:**
- `ensure_graph_indexes` exported from `docingest.db.graph_store`
- Entities unique index on `(tenant_id, name, entity_type)` present
- Relationships unique index on `(tenant_id, source_entity_id, target_entity_id, relation_type)` present
- `mongodb.py::ensure_indexes` conditionally calls `ensure_graph_indexes` when `graph_rag_enabled=True`

**Verification criteria:**
- `grep -n 'def ensure_graph_indexes' src/docingest/db/graph_store.py` returns 1 match
- `grep -n 'ensure_graph_indexes' src/docingest/db/mongodb.py` returns at least 1 match
- `grep -n 'unique=True' src/docingest/db/graph_store.py` returns at least 3 matches

**Status:** Satisfied* (no VERIFICATION.md)

---

#### GRAPH-06 — Graph data cleanup on document delete

**Code anchor:** `src/docingest/db/graph_store.py:387-416` (`delete_doc_graph_data` — function exists); `src/docingest/api/routes/documents.py::delete_document_route` (NOT called from here — the gap)
**Shipped behavior:** `delete_doc_graph_data` is implemented and correct (pulls doc_id from arrays, decrements mention_count, deletes orphans). However, the delete document API route does NOT call it. Orphaned graph data accumulates permanently when documents are deleted.

**Definition of Done (for gap-closure phase 13, not phase 12):**
- `delete_document_route` in `documents.py` imports and calls `delete_doc_graph_data` when `graph_rag_enabled`
- Deleted documents produce zero entities/relationships in MongoDB for that doc_id

**Verification criteria:**
- `grep -n 'delete_doc_graph_data' src/docingest/api/routes/documents.py` returns at least 1 call site (currently 0 — gap)

**Status:** Pending — Phase 13 (gap closure)

---

#### GRAPH-07 — `ensure_graph_indexes` helper

**Code anchor:** `src/docingest/db/graph_store.py:16-46`
**Shipped behavior:** Standalone `ensure_graph_indexes(db)` async function in `graph_store.py`. Called conditionally from both `mongodb.py::ensure_indexes` (when `graph_rag_enabled`) AND from `app.py` lifespan. The dual-call is idempotent but redundant (INT-01 tech debt, to be fixed in phase 15).

**Definition of Done:**
- `ensure_graph_indexes` is a standalone exportable async function in `graph_store.py`
- Function is callable and creates all required indexes idempotently

**Verification criteria:**
- `python -c "from docingest.db.graph_store import ensure_graph_indexes; import asyncio; print('OK')"` exits 0
- `grep -n 'def ensure_graph_indexes' src/docingest/db/graph_store.py` returns 1 match

**Status:** Satisfied* (no VERIFICATION.md)

---

### Phase 09 — Entity Extraction

#### EE-01 — spaCy `en_core_web_lg` lazy-loaded singleton

**Code anchor:** `src/docingest/services/entity_extraction.py:27-40` (`_nlp`, `_nlp_lock`, `_get_nlp`)
**Shipped behavior:** Module-level `_nlp: spacy.language.Language | None = None` and `_nlp_lock = threading.Lock()`. `_get_nlp()` uses double-checked locking identical to `embedding.py`'s `_get_model()`. Model name read from `settings.spacy_model`.

**Definition of Done:**
- `entity_extraction.py` has module-level `_nlp` and `_nlp_lock`
- `_get_nlp()` uses double-checked locking pattern (check → lock → check → load)
- Model loads from `settings.spacy_model` (default `en_core_web_lg`)

**Verification criteria:**
- `grep -n '_nlp_lock\|_get_nlp' src/docingest/services/entity_extraction.py` returns multiple matches
- `grep -n 'threading.Lock' src/docingest/services/entity_extraction.py` returns 1 match
- `pytest tests/test_entity_extraction.py::test_lazy_load -x -q` passes

**Status:** Satisfied* (no VERIFICATION.md)

---

#### EE-02 — Entity extraction per chunk with confidence filtering

**Code anchor:** `src/docingest/services/entity_extraction.py:82-107` (`extract_entities`)
**Shipped behavior:** `extract_entities(text)` runs spaCy NER, filters entities where `entity_type == EntityType.OTHER` (noise reduction), caps results at `settings.max_entities_per_chunk`. Returns list of dicts with `name`, `entity_type`, `start_char`, `end_char`.

**Definition of Done:**
- `extract_entities` exported from `docingest.services.entity_extraction`
- Returns list of dicts with keys: name, entity_type, start_char, end_char
- EntityType.OTHER entities are filtered out
- Result capped at `settings.max_entities_per_chunk`

**Verification criteria:**
- `python -c "from docingest.services.entity_extraction import extract_entities; print('OK')"` exits 0
- `grep -n 'def extract_entities' src/docingest/services/entity_extraction.py` returns 1 match
- `pytest tests/test_entity_extraction.py::test_extract_entities -x -q` passes (requires en_core_web_sm)

**Status:** Satisfied* (no VERIFICATION.md)

---

#### EE-03 — Fuzzy dedup of surface-form entities

**Code anchor:** `src/docingest/services/entity_extraction.py:177-207` (`resolve_entity`)
**Shipped behavior:** `resolve_entity(name, entity_type, existing, threshold)` uses `difflib.SequenceMatcher` to fuzzy-match candidate names against existing entities. Requires matching `entity_type`. Returns matched entity's name or None. Default threshold from `settings.entity_confidence_threshold`.

**Definition of Done:**
- `resolve_entity` exported from `docingest.services.entity_extraction`
- Entity type must match for a merge to occur
- Uses stdlib `difflib.SequenceMatcher` (no extra dependencies)
- Default threshold from `settings.entity_confidence_threshold`

**Verification criteria:**
- `python -c "from docingest.services.entity_extraction import resolve_entity; r = resolve_entity('Microsoft Corp', 'organization', [{'name': 'Microsoft Corporation', 'entity_type': 'organization'}], 0.7); assert r == 'Microsoft Corporation'; print('OK')"` exits 0
- `grep -n 'SequenceMatcher' src/docingest/services/entity_extraction.py` returns 1 match

**Status:** Satisfied* (no VERIFICATION.md)

---

#### EE-04 — SVO-based relationship extraction

**Code anchor:** `src/docingest/services/entity_extraction.py:125-169` (`extract_relationships`)
**Shipped behavior:** `extract_relationships(text, entities)` traverses spaCy dependency parse finding VERB tokens, collects nsubj/nsubjpass subjects and dobj/attr/pobj objects, expands with compound/amod modifiers via `_get_span_text`. Only includes triples where BOTH source and target match a known entity (strict filter). Returns dicts with `source`, `target`, `relation_type` (verb lemma), `description`.

**Definition of Done:**
- `extract_relationships` exported from `docingest.services.entity_extraction`
- Returns list of dicts with keys: source, target, relation_type, description
- Empty entities list → empty result (strict both-sides filter)

**Verification criteria:**
- `python -c "from docingest.services.entity_extraction import extract_relationships; r = extract_relationships('test', []); assert r == []; print('OK')"` exits 0
- `grep -n 'def extract_relationships' src/docingest/services/entity_extraction.py` returns 1 match

**Status:** Satisfied* (no VERIFICATION.md)

---

#### EE-05 — `EntityType` mapping from spaCy labels

**Code anchor:** `src/docingest/services/entity_extraction.py:47-74` (`_SPACY_LABEL_MAP`, `_map_spacy_label`)
**Shipped behavior:** `_SPACY_LABEL_MAP` dict maps all 18 spaCy NER labels to EntityType values. `_map_spacy_label(label)` performs dict lookup with `EntityType.OTHER` as default for unknown labels. Both are importable as public/private symbols.

**Definition of Done:**
- `_SPACY_LABEL_MAP` covers all 18 standard spaCy NER labels
- Unknown label falls back to `EntityType.OTHER`
- NORP, LAW, LANGUAGE, WORK_OF_ART map to CONCEPT; CARDINAL/ORDINAL/MONEY/PERCENT/QUANTITY map to OTHER

**Verification criteria:**
- `python -c "from docingest.services.entity_extraction import _SPACY_LABEL_MAP; assert len(_SPACY_LABEL_MAP) == 18; print('OK')"` exits 0
- `grep -n '_SPACY_LABEL_MAP' src/docingest/services/entity_extraction.py` returns multiple matches

**Status:** Satisfied* (no VERIFICATION.md)

---

#### EE-06 — Per-chunk limit (`MAX_ENTITIES_PER_CHUNK`)

**Code anchor:** `src/docingest/services/entity_extraction.py:107` (`entities[:settings.max_entities_per_chunk]`); `src/docingest/config.py` (`max_entities_per_chunk: int = 50`)
**Shipped behavior:** `extract_entities` slices result to `settings.max_entities_per_chunk`. Config field defaults to 50, readable from env var `MAX_ENTITIES_PER_CHUNK`.

**Definition of Done:**
- `settings.max_entities_per_chunk` field exists on Settings class with default 50
- `extract_entities` caps result at this value

**Verification criteria:**
- `python -c "from docingest.config import settings; assert settings.max_entities_per_chunk == 50; print('OK')"` exits 0
- `grep -n 'max_entities_per_chunk' src/docingest/config.py` returns 1 match

**Status:** Satisfied* (no VERIFICATION.md)

---

#### EE-07 — Configurable `ENTITY_CONFIDENCE_THRESHOLD`

**Code anchor:** `src/docingest/services/entity_extraction.py:189` (`settings.entity_confidence_threshold`); `src/docingest/config.py` (`entity_confidence_threshold: float = 0.7`)
**Shipped behavior:** `resolve_entity` uses `settings.entity_confidence_threshold` (default 0.7) as the minimum SequenceMatcher ratio. Configurable via env var `ENTITY_CONFIDENCE_THRESHOLD`.

**Definition of Done:**
- `settings.entity_confidence_threshold` field exists on Settings class with default 0.7
- `resolve_entity` uses this field as default threshold

**Verification criteria:**
- `python -c "from docingest.config import settings; assert settings.entity_confidence_threshold == 0.7; print('OK')"` exits 0
- `grep -n 'entity_confidence_threshold' src/docingest/services/entity_extraction.py` returns at least 1 match

**Status:** Satisfied* (no VERIFICATION.md)

---

#### EE-08 — Async wrappers for blocking spaCy calls

**Code anchor:** `src/docingest/services/entity_extraction.py:215-224` (`extract_entities_async`, `extract_relationships_async`)
**Shipped behavior:** Both async wrappers call `asyncio.get_event_loop().run_in_executor(None, ...)`. The `get_event_loop()` call is deprecated in Python 3.10+ (raises DeprecationWarning) and will raise `RuntimeError` in Python 3.14+. The wrappers work correctly on Python 3.12 but diverge from codebase convention (which uses `get_running_loop()`). Tech debt to be fixed in phase 15.

**Definition of Done (for gap-closure phase 15, not phase 12):**
- `extract_entities_async` and `extract_relationships_async` use `asyncio.get_running_loop()` instead of `get_event_loop()`

**Verification criteria:**
- `grep -n 'def extract_entities_async\|def extract_relationships_async' src/docingest/services/entity_extraction.py` returns 2 matches
- `grep -n 'get_running_loop' src/docingest/services/entity_extraction.py` returns 2 matches (currently 0 — gap)

**Status:** Pending — Phase 15 (gap closure)

---

### Phase 10 — Graph Builder Worker

#### GRAPH-WORKER-01 — Document `graph_status` tracked through build stages

**Code anchor:** `src/docingest/models/document.py` (graph_status, entity_count, relationship_count fields); `src/docingest/workers/graph_builder.py:73-78, 103-113, 246-256` (status updates); `src/docingest/api/routes/documents.py::_doc_to_response` (strips these fields — the gap)
**Shipped behavior:** Worker writes `graph_status` ("building"/"complete"/"failed"), `entity_count`, `relationship_count`, and `graph_built_at` to MongoDB. Document model has these fields. However `_doc_to_response` in `documents.py` omits them from `DocumentResponse`, making them invisible to API consumers.

**Definition of Done (for gap-closure phase 14, not phase 12):**
- `DocumentResponse` in `documents.py` includes `graph_status`, `entity_count`, `relationship_count`
- `GET /v1/documents/{id}` returns these fields when graph_rag_enabled

**Verification criteria:**
- `grep -n 'graph_status\|entity_count\|relationship_count' src/docingest/api/routes/documents.py` returns matches in `DocumentResponse` class (currently absent — gap)

**Status:** Pending — Phase 14 (gap closure)

---

#### GRAPH-WORKER-02 — Worker fetches chunks via `get_doc_chunks`

**Code anchor:** `src/docingest/db/qdrant.py:110-136` (`get_doc_chunks`); `src/docingest/workers/graph_builder.py:26` (import); `graph_builder.py:82` (call site)
**Shipped behavior:** `get_doc_chunks(client, tenant_id, doc_id)` performs cursor-based scroll pagination over a tenant's Qdrant collection, filtering by `doc_id` via `scroll_filter` (not `query_filter`), fetching 100 points per page, with_vectors=False. Returns all matching points. Graph builder imports and calls this at stage 2.

**Definition of Done:**
- `get_doc_chunks` exported from `src/docingest/db/qdrant.py`
- Uses `scroll_filter` (not `query_filter`) in the scroll call
- Imported and called in `src/docingest/workers/graph_builder.py`
- Returns empty list (not error) when collection exists but has no matching chunks

**Verification criteria:**
- `grep -n "def get_doc_chunks" src/docingest/db/qdrant.py` returns 1 match at line 110
- `grep -n "get_doc_chunks" src/docingest/workers/graph_builder.py` returns at least 2 matches (import + call)
- `grep -n "scroll_filter" src/docingest/db/qdrant.py` returns at least 1 match in `get_doc_chunks`

**Status:** Satisfied* (traceability added, VERIFICATION.md pending)

---

#### GRAPH-WORKER-03 — Reprocess cleans up prior graph data synchronously

**Code anchor:** `src/docingest/workers/graph_builder.py:119-121` (cleanup inside worker, fires on `version > 1` or non-None graph_status); `src/docingest/api/routes/documents.py::reprocess_document` (does NOT call delete_doc_graph_data — the gap)
**Shipped behavior:** The graph worker clears stale data before rebuilding, but only after the worker job starts (asynchronous). The reprocess API route in `documents.py` deletes Qdrant chunks but does not synchronously call `delete_doc_graph_data`, leaving a window where community rebuild can consume stale graph data.

**Definition of Done (for gap-closure phase 13, not phase 12):**
- `reprocess_document` route calls `delete_doc_graph_data` synchronously when `graph_rag_enabled`

**Verification criteria:**
- `grep -n 'delete_doc_graph_data' src/docingest/api/routes/documents.py` returns at least 1 match in `reprocess_document` function (currently 0 — gap)

**Status:** Pending — Phase 13 (gap closure)

---

#### GRAPH-WORKER-04 — Worker writes `entity_count` and `relationship_count` surfaced via API

**Code anchor:** `src/docingest/workers/graph_builder.py:246-256` (writes to MongoDB); `src/docingest/models/document.py` (fields exist on Document model)
**Shipped behavior:** Same root cause as GRAPH-WORKER-01 — fields are written to MongoDB but `_doc_to_response` in `documents.py` strips them before returning the API response.

**Definition of Done (for gap-closure phase 14, not phase 12):**
- Same as GRAPH-WORKER-01: DocumentResponse includes these fields

**Verification criteria:**
- Same as GRAPH-WORKER-01

**Status:** Pending — Phase 14 (gap closure)

---

#### GRAPH-WORKER-05 — `graph-worker` Docker service + spaCy model download

**Code anchor:** `docker/graph-worker.Dockerfile:1-11`; `docker-compose.yml` (graph-worker service block)
**Shipped behavior:** `graph-worker.Dockerfile` uses `python:3.12-slim`, copies pyproject.toml + src/, installs with pip, downloads `en_core_web_lg` via `python -m spacy download en_core_web_lg`, sets `CMD ["arq", "docingest.workers.graph_builder.WorkerSettings"]`. Docker Compose service depends on mongodb, redis, and qdrant (explicitly NOT minio), replicas: 1.

**Definition of Done:**
- `docker/graph-worker.Dockerfile` exists with `python -m spacy download en_core_web_lg` and correct CMD
- `docker-compose.yml` has a `graph-worker` service pointing to the Dockerfile

**Verification criteria:**
- `grep -n "spacy download" docker/graph-worker.Dockerfile` returns 1 match
- `grep -n "graph_builder.WorkerSettings" docker/graph-worker.Dockerfile` returns 1 match
- `grep -n "graph-worker" docker-compose.yml` returns multiple matches

**Status:** Satisfied* (traceability added, VERIFICATION.md pending)

---

### Phase 11 — Community Detection

#### COMM-01 — Leiden clustering over entity graph

**Code anchor:** `src/docingest/services/community_detection.py:31-` (`build_communities`); `_detect_communities_multi_resolution` (sync helper)
**Shipped behavior:** `build_communities` loads all tenant entities and relationships from MongoDB, builds igraph via `_build_graph`, runs Leiden via `_detect_communities_multi_resolution` using `la.CPMVertexPartition` with `resolution_parameter`. Singletons (size < 2) are filtered. All blocking calls (igraph, leidenalg) wrapped in `loop.run_in_executor`. Note: `idx_to_entity` uses `enumerate(entities)` ordering which implicitly relies on igraph vertex order matching list insertion order — fragile assumption noted in audit (to be fixed in phase 15).

**Definition of Done:**
- `build_communities` exported from `docingest.services.community_detection`
- Uses `leidenalg.CPMVertexPartition` (not ModularityVertexPartition)
- Singleton communities (< 2 entities) are filtered
- `build_communities` uses `run_in_executor` for igraph and leidenalg calls

**Verification criteria:**
- `grep -n "def build_communities" src/docingest/services/community_detection.py` returns 1 match
- `grep -n "CPMVertexPartition" src/docingest/services/community_detection.py` returns at least 1 match
- `grep -n "run_in_executor" src/docingest/services/community_detection.py` returns multiple matches

**Status:** Partial — Phase 15 (fragile idx_to_entity invariant)

---

#### COMM-02 — Multi-resolution hierarchical community detection

**Code anchor:** `src/docingest/services/community_detection.py` (`_detect_communities_multi_resolution`, parent/child linking logic in `build_communities`)
**Shipped behavior:** `_detect_communities_multi_resolution` iterates over `resolutions` list (default `[0.1, 0.5, 1.0]`), running Leiden at each level. Parent/child hierarchy is linked post-upsert by finding coarser-level community with maximum entity_ids overlap. Configuration via `settings.community_resolutions` (default `[0.1, 0.5, 1.0]`).

**Definition of Done:**
- `_detect_communities_multi_resolution` accepts a list of resolutions and returns per-level results
- `settings.community_resolutions` exists with default `[0.1, 0.5, 1.0]`
- Parent/child links are populated across levels after upserting all communities

**Verification criteria:**
- `grep -n "def _detect_communities_multi_resolution" src/docingest/services/community_detection.py` returns 1 match
- `python -c "from docingest.config import settings; assert settings.community_resolutions == [0.1, 0.5, 1.0]; print('OK')"` exits 0
- `grep -n "community_resolutions" src/docingest/config.py` returns 1 match

**Status:** Partial — Phase 15 (same fragility as COMM-01)

---

#### COMM-03 — TF-IDF extractive summaries per community

**Code anchor:** `src/docingest/services/community_detection.py` (`_extractive_summary`, `_fetch_chunk_texts`)
**Shipped behavior:** `_extractive_summary(texts, max_sentences)` uses `TfidfVectorizer(stop_words="english", max_features=5000)` to score sentences by mean TF-IDF, selects top-k in original order. `_fetch_chunk_texts(tenant_id, chunk_ids, batch_size)` scrolls Qdrant using `HasIdCondition` filter in batches. Note: `_fetch_chunk_texts` does not guard against missing collection (Qdrant throws if collection does not exist — fragile, to be fixed in phase 15).

**Definition of Done:**
- `_extractive_summary` and `_fetch_chunk_texts` both exist in `community_detection.py`
- `settings.community_max_chunks` and `settings.community_max_summary_sentences` exist with defaults 50 and 5

**Verification criteria:**
- `grep -n "def _extractive_summary\|def _fetch_chunk_texts" src/docingest/services/community_detection.py` returns 2 matches
- `python -c "from docingest.config import settings; assert settings.community_max_chunks == 50; assert settings.community_max_summary_sentences == 5; print('OK')"` exits 0

**Status:** Partial — Phase 15 (missing ensure_collection guard in `_fetch_chunk_texts`)

---

#### COMM-04 — Community embedding via FastEmbed

**Code anchor:** `src/docingest/services/community_detection.py` (`build_communities` — calls `embed_texts` via `run_in_executor`); `src/docingest/services/community_detection.py:52` (`asyncio.get_event_loop()` — deprecated)
**Shipped behavior:** Community summaries are embedded by calling `embed_texts([summary])` via `loop.run_in_executor`. The embedding vector is stored as `summary_embedding` on the community record. Uses the same FastEmbed model as chunk embeddings. Note: `loop = asyncio.get_event_loop()` at line 52 is the deprecated pattern (same issue as EE-08, to be fixed in phase 15).

**Definition of Done (for gap-closure phase 15, not phase 12):**
- `build_communities` uses `asyncio.get_running_loop()` not `get_event_loop()`

**Verification criteria:**
- `grep -n "embed_texts" src/docingest/services/community_detection.py` returns at least 1 match
- `grep -n "get_running_loop" src/docingest/services/community_detection.py` returns at least 1 match (currently 0 — gap)

**Status:** Partial — Phase 15 (gap closure: asyncio deprecation)

---

#### COMM-05 — `POST /v1/graph/communities/rebuild` API route

**Code anchor:** `src/docingest/api/routes/graph.py:17-33` (`rebuild_communities` function); `src/docingest/api/app.py:65` (`app.include_router(graph.router, prefix="/v1", ...)`)
**Shipped behavior:** `POST /v1/graph/communities/rebuild` endpoint authenticated via `Tenant` dependency (API key + rate limiting). Returns 403 when `settings.graph_rag_enabled` is False. Calls `build_communities(db, tenant["tenant_id"])` and returns `{"status": "ok", "communities": stats}`. Structured logging for rebuild start and complete. Router mounted in `app.py` under `/v1` prefix at lifespan-aware startup.

**Definition of Done:**
- `src/docingest/api/routes/graph.py` exists with `POST /communities/rebuild` endpoint
- Route returns HTTP 403 when `graph_rag_enabled=False`
- Router mounted in `app.py` under `/v1` prefix
- `ensure_graph_indexes` called in lifespan when `graph_rag_enabled=True`

**Verification criteria:**
- `grep -n "def rebuild_communities" src/docingest/api/routes/graph.py` returns 1 match
- `grep -n "graph.router" src/docingest/api/app.py` returns 1 match
- `grep -n "graph_rag_enabled" src/docingest/api/routes/graph.py` returns at least 1 match (the 403 gate)
- `grep -n "ensure_graph_indexes" src/docingest/api/app.py` returns 1 match

**Status:** Satisfied* (traceability added, VERIFICATION.md pending)

---

## Artifact Edit Plan

### 1. REQUIREMENTS.md

**File:** `.planning/REQUIREMENTS.md`
**Current state (lines 1-70):** Skeleton entries (label + phase + status only). No descriptions, DoDs, or verification criteria. Footer note at line 63 explicitly calls for phase 12 to expand this.

**What changes:**
- Expand each of the 25 REQ-ID entries from single-line checkbox items to multi-line entries following the locked schema (Description, DoD bullets, Verification criteria bullets, Status)
- Flip statuses for GRAPH-WORKER-02, GRAPH-WORKER-05, COMM-05 from `Pending — phase 12` to `Satisfied* (traceability added, VERIFICATION.md pending)`
- Remove the "Notes for Phase 12" footer section (it becomes obsolete once phase 12 executes)

**Anchor:** Entire body of file — all 70 lines are rewritten. The header (lines 1-19, coverage table) should be preserved and updated. Each section heading (`## Graph Data Models`, etc.) is preserved.

**Content source:** The REQ-ID Inventory section above contains all prose, DoD bullets, and verification criteria ready to paste.

**Cross-reference risks:**
- The existing status values are referenced by `.planning/v1.0-MILESTONE-AUDIT.md` (read-only — no edit needed, it's the audit source not a consumer)
- No other file imports or parses REQUIREMENTS.md programmatically

---

### 2. PROJECT.md

**File:** `.planning/PROJECT.md`
**Current state:** Last line is `*Last updated: 2026-03-04 after v1.0 milestone*`

**What changes (three edits):**

1. **Out of Scope section (line 42):** Remove the line `- Graph RAG / knowledge graph — research-grade complexity for marginal gains`

2. **Validated requirements section (after line 24, currently the last validated item):** Add two new items:
   ```
   - ✓ Graph RAG pipeline: entity extraction (spaCy NER + SVO relationships), knowledge graph storage (MongoDB entities/relationships), and community detection (multi-resolution Leiden + TF-IDF summaries) — v1.0 extension
   - ✓ Feature gating: `GRAPH_RAG_ENABLED` environment flag controls graph pipeline activation end-to-end (lifespan, chunker enqueue, worker, API) — v1.0 extension
   ```

3. **Context block (line 47, currently ends at v1.0 LOC count):** Add a sentence after the existing context lines:
   ```
   Extended with Graph RAG pipeline post-ship (phases 8-11, 2026-04-12): entity/relationship extraction via spaCy, MongoDB graph store, Leiden community detection. See `.planning/v1.0-MILESTONE-AUDIT.md` for gap analysis.
   ```

4. **Last updated line (line 77):** Change to `*Last updated: 2026-04-16 after v1.0 gap closure planning*`

**Cross-reference risks:**
- The `Active` section currently reads `(None yet — define requirements for next milestone)`. This phrasing remains valid since Graph RAG items are in Validated, not Active.
- No other planning files reference PROJECT.md by line number.

---

### 3. MILESTONES.md

**File:** `.planning/MILESTONES.md`
**Current state (lines 1-28):** Single `## v1.0 MVP (Shipped: 2026-03-04)` block ending with `**What's next:** TBD — next milestone discussion needed`

**What changes:** Append a new `### v1.0 Graph RAG Extension (2026-04-12)` subsection after the existing v1.0 MVP block (after line 27). The CONTEXT.md provides the exact shape for this block (verbatim in `<specifics>`).

**Anchor:** Insert after line 27 (the `---` separator), before the closing of the file.

**Content to add (from CONTEXT.md specifics):**
```markdown
### v1.0 Graph RAG Extension (2026-04-12)

**Delivered:** Knowledge-graph pipeline layered onto v1.0 MVP — spaCy-based entity/relationship extraction over chunked content, MongoDB graph store with tenant isolation, and on-demand Leiden community detection with TF-IDF summaries. All functionality gated by `GRAPH_RAG_ENABLED`.

**Phases:** 8-11 (7 plans)
**Requirements declared:** 25 (GRAPH-01..07, EE-01..08, GRAPH-WORKER-01..05, COMM-01..05)
**Status:** ⚠ Gap closure in flight (phases 12-15) — see `.planning/v1.0-MILESTONE-AUDIT.md`.

**Stats:**
- graph-worker: new ARQ worker with dedicated queue (`arq:queue:graph`)
- New services: `entity_extraction`, `community_detection`
- New models: Entity, Relationship, Community
- New dependencies: spaCy (`en_core_web_lg`), python-igraph, leidenalg, scikit-learn

**Git range:** `85e5a0e` (v1.0 ship) → `479736f` (gap closure phases added)
```

**Cross-reference risks:** None. MILESTONES.md is a standalone narrative document not parsed by any script.

---

### 4. 10-01-SUMMARY.md

**File:** `.planning/phases/10-graph-builder-worker/10-01-SUMMARY.md`
**Current state (lines 1-33):** Frontmatter block ends at line 33 with `---`. No `requirements-completed` key present.

**What changes:** Add `requirements-completed: [GRAPH-WORKER-01, GRAPH-WORKER-02, GRAPH-WORKER-03, GRAPH-WORKER-04, GRAPH-WORKER-05]` to the YAML frontmatter, immediately before the closing `---` on line 33.

**Anchor:** Between `files: 7` (line 32) and `---` (line 33).

**Reference shape:** `08-01-SUMMARY.md` line 33: `requirements-completed: [GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-07]`

**Cross-reference risks:**
- Rationale for including GRAPH-WORKER-01, 03, 04: These are partial in the audit (wiring shipped, API surfacing didn't). The CONTEXT.md decision locked that SUMMARY frontmatter reflects what was "delivered by that plan", not the audit verdict. The audit verdict nuance lives in REQUIREMENTS.md status field.
- No tool parses this frontmatter in an automated assertion currently.

---

### 5. 11-01-SUMMARY.md

**File:** `.planning/phases/11-community-detection/11-01-SUMMARY.md`
**Current state (lines 1-29):** Frontmatter ends at line 29 with `---`. No `requirements-completed` key.

**What changes:** Add `requirements-completed: [COMM-01, COMM-02, COMM-03, COMM-04]` to frontmatter before closing `---`.

**Note on COMM-04:** The 11-01-PLAN.md `requirements:` frontmatter lists only `[COMM-01, COMM-02, COMM-03]`. However, the 11-02-PLAN.md lists `requirements: [COMM-04, COMM-05]`. The CONTEXT.md decision table assigns COMM-01..04 to 11-01-SUMMARY and COMM-05 to 11-02-SUMMARY. This means COMM-04 frontmatter is split from what the 11-02-PLAN declared. The planner should follow the CONTEXT.md locked decision (COMM-04 goes in 11-01-SUMMARY) since COMM-04 is the embedding service itself (implemented in 11-01), while 11-02 added the tests and API. The CONTEXT.md decision is intentional.

**Anchor:** Between `files: 3` (line 28) and `---` (line 29).

---

### 6. 11-02-SUMMARY.md

**File:** `.planning/phases/11-community-detection/11-02-SUMMARY.md`
**Current state (lines 1-27):** Frontmatter ends at line 27 with `---`. No `requirements-completed` key.

**What changes:** Add `requirements-completed: [COMM-05]` to frontmatter before closing `---`.

**Anchor:** Between `files: 3` (line 26) and `---` (line 27).

---

## Risks and Surprises

### 1. COMM-04 SUMMARY Ownership Discrepancy (MEDIUM)

**What it is:** The 11-02-PLAN.md declares `requirements: [COMM-04, COMM-05]`. The CONTEXT.md assigns COMM-04 to 11-01-SUMMARY.md, not 11-02. This means the executor will add COMM-04 to 11-01-SUMMARY but not to 11-02-SUMMARY, which is technically inconsistent with the plan's declared requirements.

**Root cause:** The implementation of COMM-04 (embedding via FastEmbed in `build_communities`) happened in 11-01. The 11-02 plan only added tests and the API. The CONTEXT.md correctly attributes delivery credit to 11-01.

**Risk:** A future `/gsd:verify-work` scan that checks "does SUMMARY.requirements-completed match PLAN.requirements" will find COMM-04 in 11-01-SUMMARY but the 11-02-PLAN.md declares it. This is a pre-existing inconsistency in the original plan authoring — not introduced by phase 12. Phase 12 cannot fix this without touching 11-02-PLAN.md (which is out of scope).

**Mitigation:** Document the discrepancy in the REQUIREMENTS.md COMM-04 entry notes, or add a prose note in 11-01-SUMMARY's body. The planner can choose to add a comment.

### 2. INT-01 Dual ensure_graph_indexes Call Is Visible After Phase 12 (LOW)

**What it is:** `mongodb.py::ensure_indexes` calls `_ensure_graph_indexes(db)` conditionally, AND `app.py` lifespan calls `ensure_graph_indexes(db)` conditionally. Both are gated by `graph_rag_enabled`. After phase 12 documents GRAPH-07 as Satisfied*, a future reader will see this dual-call pattern.

**Risk:** Minimal — the calls are idempotent. Not a phase 12 problem. Phase 15 closes INT-01.

**Mitigation:** The GRAPH-07 DoD entry should mention this known dual-call without marking it as a gap (it's tech debt, not a requirements failure).

### 3. REQUIREMENTS.md File Is a Full Rewrite (LOW)

**What it is:** The current REQUIREMENTS.md is 70 lines. The fully-expanded version will be ~400+ lines. The executor should use the `Write` tool (full overwrite), not the `Edit` tool, to avoid complex patch failures on a file being substantially expanded.

**Risk:** Low — Write tool overwrites cleanly. The risk is accidentally truncating the file or losing the header block.

**Mitigation:** Executor should read the current file first (already done in this research), write the complete new version including the unchanged header lines 1-19, and verify line count afterward.

### 4. PROJECT.md Active Section (LOW)

**What it is:** `PROJECT.md` line 29-30 reads `### Active\n\n(None yet — define requirements for next milestone)`. After adding Graph RAG items to Validated, the Active section still says "None". This is technically correct (Graph RAG is in Validated, not Active) but may look odd since gap-closure phases 12-15 are actively in flight.

**Risk:** Cosmetic only. Active section is for defined requirements awaiting implementation; gap-closure phases aren't "requirements" in that sense.

**Mitigation:** Leave Active as-is per locked decisions. Do not add gap-closure work to Active.

### 5. No Script or Test Parses Planning Files (CONFIRMED LOW)

Verified by inspection: no test file in `tests/` parses MILESTONES.md, PROJECT.md, REQUIREMENTS.md, or SUMMARY frontmatter. The planning files are consumed by humans and AI agents only. Edit failures will be caught by the Nyquist grep-checks below, not by automated tests.

---

## Validation Architecture

Config: `workflow.nyquist_validation` key is absent from `.planning/config.json` — treat as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | grep (shell), not pytest — docs-only phase |
| Config file | none |
| Quick run command | `grep -r "GRAPH-WORKER-02\|GRAPH-WORKER-05\|COMM-05" .planning/REQUIREMENTS.md` |
| Full suite command | See Phase Gate checks below |

### Phase Requirements to Validation Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-WORKER-02 | Status flipped to Satisfied* in REQUIREMENTS.md | content-check | `grep "GRAPH-WORKER-02" .planning/REQUIREMENTS.md \| grep "Satisfied\*"` | ✅ (after 12-01) |
| GRAPH-WORKER-05 | Status flipped to Satisfied* in REQUIREMENTS.md | content-check | `grep "GRAPH-WORKER-05" .planning/REQUIREMENTS.md \| grep "Satisfied\*"` | ✅ (after 12-01) |
| COMM-05 | Status flipped to Satisfied* in REQUIREMENTS.md | content-check | `grep "COMM-05" .planning/REQUIREMENTS.md \| grep "Satisfied\*"` | ✅ (after 12-01) |

### Artifact-Presence Checks (all must pass before phase gate)

```bash
# 1. REQUIREMENTS.md has all 25 REQ-IDs
for id in GRAPH-01 GRAPH-02 GRAPH-03 GRAPH-04 GRAPH-05 GRAPH-06 GRAPH-07 \
           EE-01 EE-02 EE-03 EE-04 EE-05 EE-06 EE-07 EE-08 \
           GRAPH-WORKER-01 GRAPH-WORKER-02 GRAPH-WORKER-03 GRAPH-WORKER-04 GRAPH-WORKER-05 \
           COMM-01 COMM-02 COMM-03 COMM-04 COMM-05; do
  grep -q "$id" .planning/REQUIREMENTS.md || echo "MISSING: $id"
done

# 2. Each expanded entry has Description, DoD, and Verification sections
grep -c "Definition of Done" .planning/REQUIREMENTS.md  # expect 25
grep -c "Verification criteria" .planning/REQUIREMENTS.md  # expect 25

# 3. PROJECT.md no longer lists Graph RAG as out-of-scope
grep -c "Graph RAG / knowledge graph" .planning/PROJECT.md  # expect 0

# 4. PROJECT.md has v1.0 extension entries in Validated section
grep -c "v1.0 extension" .planning/PROJECT.md  # expect >= 2

# 5. MILESTONES.md has Graph RAG extension block
grep -q "v1.0 Graph RAG Extension" .planning/MILESTONES.md && echo "OK"

# 6. 10-01-SUMMARY.md has requirements-completed frontmatter
grep -q "requirements-completed:" .planning/phases/10-graph-builder-worker/10-01-SUMMARY.md && echo "OK"
grep -q "GRAPH-WORKER-02" .planning/phases/10-graph-builder-worker/10-01-SUMMARY.md && echo "OK"

# 7. 11-01-SUMMARY.md has requirements-completed frontmatter
grep -q "requirements-completed:" .planning/phases/11-community-detection/11-01-SUMMARY.md && echo "OK"
grep -q "COMM-01" .planning/phases/11-community-detection/11-01-SUMMARY.md && echo "OK"

# 8. 11-02-SUMMARY.md has requirements-completed frontmatter
grep -q "requirements-completed:" .planning/phases/11-community-detection/11-02-SUMMARY.md && echo "OK"
grep -q "COMM-05" .planning/phases/11-community-detection/11-02-SUMMARY.md && echo "OK"

# 9. Status flips applied
grep "GRAPH-WORKER-02" .planning/REQUIREMENTS.md | grep -q "Satisfied\*"
grep "GRAPH-WORKER-05" .planning/REQUIREMENTS.md | grep -q "Satisfied\*"
grep "COMM-05" .planning/REQUIREMENTS.md | grep -q "Satisfied\*"

# 10. Cross-reference consistency: every REQ-ID in REQUIREMENTS.md appears in at least one PLAN requirements: frontmatter
#     (These are the known canonical PLAN sources — no new REQ-IDs should be invented)
grep -q "GRAPH-01" .planning/phases/08-graph-data-models/08-01-PLAN.md && echo "GRAPH-01 in plan OK"
grep -q "COMM-05" .planning/phases/11-community-detection/11-02-PLAN.md && echo "COMM-05 in plan OK"
```

### Sampling Rate

- **Per task commit:** Run artifact-presence check for the specific file modified
- **Per wave:** Run full suite of 10 checks above
- **Phase gate:** All 10 checks green before `/gsd:verify-work`

### Wave 0 Gaps

None — this is a docs-only phase. No test infrastructure is required. All validation is grep-based.

---

## Sources

### Primary (HIGH confidence)

All findings are from direct file reads — no external sources consulted.

| File | Purpose |
|------|---------|
| `src/docingest/models/graph.py` | GRAPH-01, 02, 03 DoD and verification |
| `src/docingest/db/graph_store.py` | GRAPH-04, 05, 06, 07 DoD and verification |
| `src/docingest/services/entity_extraction.py` | EE-01 through EE-08 DoD and verification |
| `src/docingest/db/qdrant.py:110-136` | GRAPH-WORKER-02 DoD and verification |
| `src/docingest/workers/graph_builder.py` | GRAPH-WORKER-01, 02, 03, 04, 05 DoD and verification |
| `docker/graph-worker.Dockerfile` | GRAPH-WORKER-05 DoD and verification |
| `src/docingest/services/community_detection.py` | COMM-01, 02, 03, 04 DoD and verification |
| `src/docingest/api/routes/graph.py` | COMM-05 DoD and verification |
| `src/docingest/api/app.py` | COMM-05 router mount verification |
| `.planning/phases/08-*/08-0[12]-PLAN.md` | GRAPH-* canonical REQ-ID declarations |
| `.planning/phases/09-*/09-01-PLAN.md` | EE-* canonical REQ-ID declarations |
| `.planning/phases/10-*/PLAN.md` | GRAPH-WORKER-* canonical REQ-ID declarations |
| `.planning/phases/11-*/11-0[12]-PLAN.md` | COMM-* canonical REQ-ID declarations |
| `.planning/v1.0-MILESTONE-AUDIT.md` | Audit evidence for gap/orphan classification |
| `.planning/phases/12-graph-rag-traceability/12-CONTEXT.md` | All locked decisions |

---

## Metadata

**Confidence breakdown:**
- REQ-ID inventory: HIGH — read from actual source files, not inferred
- Artifact edit plan: HIGH — current file state read directly, anchor lines verified
- Risks: MEDIUM — identified by cross-referencing CONTEXT.md decisions with code reality
- Validation architecture: HIGH — grep commands verified against real file paths

**Research date:** 2026-04-16
**Valid until:** Stable indefinitely — docs-only phase, no external dependencies
