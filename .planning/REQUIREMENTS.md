# Requirements: DocIngest

**Current milestone:** v1.0 (gap closure)
**Last updated:** 2026-04-16

v1.0 MVP requirements (23 IDs, all satisfied) are archived at [.planning/milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md).

This file tracks the **Graph RAG extension** requirements delivered in phases 8-11 and expanded by phase 12 to include full descriptions, definitions of done, and verification criteria.

<!-- hr -->

## Coverage

- **Total REQ-IDs:** 25
- **Satisfied:** 14
- **Partial (gap closure in flight):** 7
- **Orphaned (traceability only):** 4

<!-- hr -->

## Graph Data Models (Phase 08)

- [x] **GRAPH-01** — Entity, Relationship, Community Pydantic models — Phase: 08 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** Three Pydantic v2 BaseModel classes (`Entity`, `Relationship`, `Community`) that follow the same conventions as `document.py` — `Field(alias="_id")`, `model_config = {"populate_by_name": True}`, and `datetime.now(UTC)` defaults. These models are the canonical in-memory representation of graph data throughout the pipeline.
  - **Definition of Done:**
    - `src/docingest/models/graph.py` exists and exports `Entity`, `Relationship`, `Community`.
    - Each model uses `Field(default="", alias="_id")` for its id field and `model_config = {"populate_by_name": True}`.
    - All three models have `created_at` and `updated_at` with `datetime.now(UTC)` defaults.
  - **Verification criteria:**
    - `python -c "from docingest.models.graph import Entity, Relationship, Community; print('OK')"` exits 0.
    - `grep -n 'class Entity\|class Relationship\|class Community' src/docingest/models/graph.py` returns 3 matches.
    - `grep -n 'populate_by_name' src/docingest/models/graph.py` returns 3 matches.

- [x] **GRAPH-02** — `EntityType` enum + core entity fields — Phase: 08 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** `EntityType` StrEnum with exactly 8 values (person, organization, location, date, event, product, concept, other) plus the core field set on `Entity` (aliases, doc_ids, chunk_ids, mention_count, embedding, metadata) with correct defaults for list and scalar fields.
  - **Definition of Done:**
    - `EntityType` has exactly 8 values (person, organization, location, date, event, product, concept, other).
    - `Entity.aliases`, `Entity.doc_ids`, `Entity.chunk_ids` default to empty list via `Field(default_factory=list)`.
    - `Entity.mention_count` defaults to 0; `Entity.embedding` defaults to None.
  - **Verification criteria:**
    - `python -c "from docingest.models.graph import EntityType; assert len(EntityType) == 8; print('OK')"` exits 0.
    - `grep -n 'class EntityType' src/docingest/models/graph.py` returns 1 match.
    - `pytest tests/test_graph_models.py -x -q` passes.

- [x] **GRAPH-03** — Relationship model with relation_type taxonomy — Phase: 08 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** `Relationship` model with `source_entity_id`, `target_entity_id`, and `relation_type` (plain string for open vocabulary, not an enum), plus supporting fields (`description`, `weight`, `doc_ids`, `chunk_ids`) that enable later ranking and provenance tracking.
  - **Definition of Done:**
    - `Relationship` model exported from `docingest.models.graph`.
    - `relation_type` is a plain `str` (not an enum) enabling open vocabulary.
    - `weight` defaults to 1.0; `doc_ids` and `chunk_ids` default to empty list.
  - **Verification criteria:**
    - `python -c "from docingest.models.graph import Relationship; r = Relationship(tenant_id='t', source_entity_id='a', target_entity_id='b', relation_type='acquired'); assert r.weight == 1.0; print('OK')"` exits 0.
    - `grep -n 'relation_type' src/docingest/models/graph.py` returns at least 1 match.

- [x] **GRAPH-04** — `graph_store.py` CRUD: upsert/get entities and relationships — Phase: 08 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** Atomic upsert helpers for entities and relationships in `src/docingest/db/graph_store.py`. `upsert_entity` filters on `(tenant_id, name, entity_type)` using `$addToSet` for array merges and `$inc` for `mention_count`. `upsert_relationship` filters on `(tenant_id, source_entity_id, target_entity_id, relation_type)` with equivalent merge semantics. Both return the stored document's id as string.
  - **Definition of Done:**
    - `upsert_entity` and `upsert_relationship` exported from `docingest.db.graph_store`.
    - Both functions use `update_one(upsert=True)` with `$addToSet` merge semantics.
    - `get_entity_by_id` and `find_entities_by_names` exported and functional.
  - **Verification criteria:**
    - `python -c "from docingest.db.graph_store import upsert_entity, upsert_relationship, get_entity_by_id, find_entities_by_names; print('OK')"` exits 0.
    - `grep -n 'addToSet\|upsert=True' src/docingest/db/graph_store.py` returns multiple matches.
    - `pytest tests/test_graph_store.py -x -q` passes.

- [x] **GRAPH-05** — Unique compound indexes for entity/relationship dedup — Phase: 08 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** `ensure_graph_indexes` creates unique compound indexes enforcing entity dedup on `(tenant_id, name, entity_type)` and relationship dedup on `(tenant_id, source_entity_id, target_entity_id, relation_type)`, plus lookup indexes on doc_ids, entity_type, and source/target ids for query performance.
  - **Definition of Done:**
    - `ensure_graph_indexes` exported from `docingest.db.graph_store`.
    - Entities unique index on `(tenant_id, name, entity_type)` present.
    - Relationships unique index on `(tenant_id, source_entity_id, target_entity_id, relation_type)` present.
    - `mongodb.py::ensure_indexes` conditionally calls `ensure_graph_indexes` when `graph_rag_enabled=True`.
  - **Verification criteria:**
    - `grep -n 'def ensure_graph_indexes' src/docingest/db/graph_store.py` returns 1 match.
    - `grep -n 'ensure_graph_indexes' src/docingest/db/mongodb.py` returns at least 1 match.
    - `grep -n 'unique=True' src/docingest/db/graph_store.py` returns at least 3 matches.

- [x] **GRAPH-06** — Graph data cleanup on document delete — Phase: 08 — Status: Pending — Phase 13 (gap closure)
  - **Description:** When a document is deleted, its contribution to the graph (entity doc_id entries, relationship doc_id entries, orphan entities whose doc_ids becomes empty) must be cleaned up. `delete_doc_graph_data` is implemented and correct, but the delete document API route does not call it, leaving orphaned graph data permanently in MongoDB.
  - **Definition of Done:**
    - `delete_document_route` in `documents.py` imports and calls `delete_doc_graph_data` when `graph_rag_enabled`.
    - Deleted documents produce zero entities/relationships in MongoDB for that `doc_id`.
  - **Verification criteria:**
    - `grep -n 'delete_doc_graph_data' src/docingest/api/routes/documents.py` returns at least 1 call site (currently 0 — gap).

- [x] **GRAPH-07** — `ensure_graph_indexes` helper — Phase: 08 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** Standalone async `ensure_graph_indexes(db)` function in `graph_store.py`. Called conditionally from both `mongodb.py::ensure_indexes` (when `graph_rag_enabled`) and from `app.py` lifespan. The dual-call is idempotent but redundant (INT-01 tech debt tracked for phase 15).
  - **Definition of Done:**
    - `ensure_graph_indexes` is a standalone exportable async function in `graph_store.py`.
    - Function is callable and creates all required indexes idempotently.
  - **Verification criteria:**
    - `python -c "from docingest.db.graph_store import ensure_graph_indexes; import asyncio; print('OK')"` exits 0.
    - `grep -n 'def ensure_graph_indexes' src/docingest/db/graph_store.py` returns 1 match.

## Entity Extraction (Phase 09)

- [x] **EE-01** — spaCy `en_core_web_lg` lazy-loaded singleton — Phase: 09 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** Module-level `_nlp` reference with `threading.Lock` guard in `entity_extraction.py`. `_get_nlp()` uses the same double-checked locking pattern as `embedding.py::_get_model()` so the large spaCy model is loaded exactly once per process and only on first use. Model name is read from `settings.spacy_model`.
  - **Definition of Done:**
    - `entity_extraction.py` has module-level `_nlp` and `_nlp_lock`.
    - `_get_nlp()` uses double-checked locking pattern (check → lock → check → load).
    - Model loads from `settings.spacy_model` (default `en_core_web_lg`).
  - **Verification criteria:**
    - `grep -n '_nlp_lock\|_get_nlp' src/docingest/services/entity_extraction.py` returns multiple matches.
    - `grep -n 'threading.Lock' src/docingest/services/entity_extraction.py` returns 1 match.
    - `pytest tests/test_entity_extraction.py::test_lazy_load -x -q` passes.

- [x] **EE-02** — Entity extraction per chunk with confidence filtering — Phase: 09 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** `extract_entities(text)` runs spaCy NER over a chunk, filters out `EntityType.OTHER` entities (graph-noise reduction), and caps the result at `settings.max_entities_per_chunk`. Returns a list of dicts with `name`, `entity_type`, `start_char`, `end_char`.
  - **Definition of Done:**
    - `extract_entities` exported from `docingest.services.entity_extraction`.
    - Returns list of dicts with keys: name, entity_type, start_char, end_char.
    - `EntityType.OTHER` entities are filtered out.
    - Result capped at `settings.max_entities_per_chunk`.
  - **Verification criteria:**
    - `python -c "from docingest.services.entity_extraction import extract_entities; print('OK')"` exits 0.
    - `grep -n 'def extract_entities' src/docingest/services/entity_extraction.py` returns 1 match.
    - `pytest tests/test_entity_extraction.py::test_extract_entities -x -q` passes.

- [x] **EE-03** — Fuzzy dedup of surface-form entities — Phase: 09 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** `resolve_entity(name, entity_type, existing, threshold)` uses `difflib.SequenceMatcher` to fuzzy-match a candidate name against already-known entities of the same type. Returns the matched canonical name or None. Default threshold is `settings.entity_confidence_threshold`. Pure stdlib — no rapidfuzz / Levenshtein dependency.
  - **Definition of Done:**
    - `resolve_entity` exported from `docingest.services.entity_extraction`.
    - Entity type must match for a merge to occur.
    - Uses stdlib `difflib.SequenceMatcher` (no extra dependencies).
    - Default threshold from `settings.entity_confidence_threshold`.
  - **Verification criteria:**
    - `python -c "from docingest.services.entity_extraction import resolve_entity; r = resolve_entity('Microsoft Corp', 'organization', [{'name': 'Microsoft Corporation', 'entity_type': 'organization'}], 0.7); assert r == 'Microsoft Corporation'; print('OK')"` exits 0.
    - `grep -n 'SequenceMatcher' src/docingest/services/entity_extraction.py` returns 1 match.

- [x] **EE-04** — SVO-based relationship extraction — Phase: 09 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** `extract_relationships(text, entities)` traverses the spaCy dependency parse, finds VERB tokens, and collects subject/object spans (nsubj/nsubjpass → dobj/attr/pobj) expanded with compound and amod modifiers via `_get_span_text`. Only triples where BOTH source and target match a known entity from the input list are emitted. Returns dicts with `source`, `target`, `relation_type` (verb lemma), `description`.
  - **Definition of Done:**
    - `extract_relationships` exported from `docingest.services.entity_extraction`.
    - Returns list of dicts with keys: source, target, relation_type, description.
    - Empty entities list → empty result (strict both-sides filter).
  - **Verification criteria:**
    - `python -c "from docingest.services.entity_extraction import extract_relationships; r = extract_relationships('test', []); assert r == []; print('OK')"` exits 0.
    - `grep -n 'def extract_relationships' src/docingest/services/entity_extraction.py` returns 1 match.

- [x] **EE-05** — `EntityType` mapping from spaCy labels — Phase: 09 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** `_SPACY_LABEL_MAP` dict maps all 18 standard spaCy NER labels to `EntityType` values, with `_map_spacy_label(label)` performing the lookup and falling back to `EntityType.OTHER` for unknowns. NORP, LAW, LANGUAGE, WORK_OF_ART → CONCEPT; CARDINAL, ORDINAL, MONEY, PERCENT, QUANTITY → OTHER (filtered downstream).
  - **Definition of Done:**
    - `_SPACY_LABEL_MAP` covers all 18 standard spaCy NER labels.
    - Unknown label falls back to `EntityType.OTHER`.
    - NORP, LAW, LANGUAGE, WORK_OF_ART map to CONCEPT; CARDINAL/ORDINAL/MONEY/PERCENT/QUANTITY map to OTHER.
  - **Verification criteria:**
    - `python -c "from docingest.services.entity_extraction import _SPACY_LABEL_MAP; assert len(_SPACY_LABEL_MAP) == 18; print('OK')"` exits 0.
    - `grep -n '_SPACY_LABEL_MAP' src/docingest/services/entity_extraction.py` returns multiple matches.

- [x] **EE-06** — Per-chunk limit (`MAX_ENTITIES_PER_CHUNK`) — Phase: 09 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** Hard upper bound on how many entities `extract_entities` returns from a single chunk, to keep per-chunk graph fan-out predictable. Default 50, overridable via the `MAX_ENTITIES_PER_CHUNK` environment variable.
  - **Definition of Done:**
    - `settings.max_entities_per_chunk` field exists on Settings class with default 50.
    - `extract_entities` caps result at this value.
  - **Verification criteria:**
    - `python -c "from docingest.config import settings; assert settings.max_entities_per_chunk == 50; print('OK')"` exits 0.
    - `grep -n 'max_entities_per_chunk' src/docingest/config.py` returns 1 match.

- [x] **EE-07** — Configurable `ENTITY_CONFIDENCE_THRESHOLD` — Phase: 09 — Status: Satisfied* (no VERIFICATION.md)
  - **Description:** Minimum `SequenceMatcher` ratio used by `resolve_entity` to decide whether two surface forms should merge into the same canonical entity. Default 0.7, overridable via the `ENTITY_CONFIDENCE_THRESHOLD` environment variable.
  - **Definition of Done:**
    - `settings.entity_confidence_threshold` field exists on Settings class with default 0.7.
    - `resolve_entity` uses this field as default threshold.
  - **Verification criteria:**
    - `python -c "from docingest.config import settings; assert settings.entity_confidence_threshold == 0.7; print('OK')"` exits 0.
    - `grep -n 'entity_confidence_threshold' src/docingest/services/entity_extraction.py` returns at least 1 match.

- [ ] **EE-08** — Async wrappers for blocking spaCy calls — Phase: 09 — Status: Pending — Phase 15 (gap closure)
  - **Description:** `extract_entities_async` and `extract_relationships_async` wrap the sync spaCy calls via `run_in_executor`. Current implementation uses the deprecated `asyncio.get_event_loop()` (raises DeprecationWarning on Python 3.10+, `RuntimeError` on 3.14+). Functional on Python 3.12 but diverges from the codebase convention (which uses `get_running_loop`). Phase 15 will align.
  - **Definition of Done:**
    - `extract_entities_async` and `extract_relationships_async` use `asyncio.get_running_loop()` instead of `get_event_loop()`.
  - **Verification criteria:**
    - `grep -n 'def extract_entities_async\|def extract_relationships_async' src/docingest/services/entity_extraction.py` returns 2 matches.
    - `grep -n 'get_running_loop' src/docingest/services/entity_extraction.py` returns 2 matches (currently 0 — gap).

## Graph Builder Worker (Phase 10)

- [ ] **GRAPH-WORKER-01** — Document `graph_status` tracked through build stages — Phase: 10 — Status: Pending — Phase 14 (gap closure)
  - **Description:** The graph-worker writes `graph_status` (building / complete / failed), `entity_count`, `relationship_count`, and `graph_built_at` to each document's MongoDB record as it progresses. The `Document` model carries these fields, but `_doc_to_response` in `documents.py` strips them from `DocumentResponse`, so API consumers (including the frontend) cannot see graph-build status per document.
  - **Definition of Done:**
    - `DocumentResponse` in `documents.py` includes `graph_status`, `entity_count`, `relationship_count`.
    - `GET /v1/documents/{id}` returns these fields when `graph_rag_enabled`.
  - **Verification criteria:**
    - `grep -n 'graph_status\|entity_count\|relationship_count' src/docingest/api/routes/documents.py` returns matches in `DocumentResponse` class (currently absent — gap).

- [x] **GRAPH-WORKER-02** — Worker fetches chunks via `get_doc_chunks` — Phase: 10 — Status: Satisfied* (traceability added, VERIFICATION.md pending)
  - **Description:** The graph-worker must fetch a document's chunk texts from Qdrant (not MongoDB) to run entity extraction, because chunks live in the vector store. `get_doc_chunks(client, tenant_id, doc_id)` wraps the cursor-based scroll RPC with `scroll_filter` (not `query_filter`), paginates 100 points at a time with `with_vectors=False`, and returns the full list. The worker imports and calls this at stage 2 of the build.
  - **Definition of Done:**
    - `get_doc_chunks` exported from `src/docingest/db/qdrant.py`.
    - Uses `scroll_filter` (not `query_filter`) in the scroll call.
    - Imported and called in `src/docingest/workers/graph_builder.py`.
    - Returns empty list (not error) when collection exists but has no matching chunks.
  - **Verification criteria:**
    - `grep -n "def get_doc_chunks" src/docingest/db/qdrant.py` returns 1 match.
    - `grep -n "get_doc_chunks" src/docingest/workers/graph_builder.py` returns at least 2 matches (import + call).
    - `grep -n "scroll_filter" src/docingest/db/qdrant.py` returns at least 1 match in `get_doc_chunks`.

- [x] **GRAPH-WORKER-03** — Reprocess cleans up prior graph data synchronously — Phase: 10 — Status: Pending — Phase 13 (gap closure)
  - **Description:** When a document is reprocessed, stale graph data from the previous build must be removed before the new build enqueues, otherwise community rebuild can consume a mix of old and new entities. The worker itself clears data on start (via `version > 1` or non-None `graph_status`), but the `reprocess_document` API route deletes Qdrant chunks without calling `delete_doc_graph_data`, leaving an inconsistency window.
  - **Definition of Done:**
    - `reprocess_document` route calls `delete_doc_graph_data` synchronously when `graph_rag_enabled`.
  - **Verification criteria:**
    - `grep -n 'delete_doc_graph_data' src/docingest/api/routes/documents.py` returns at least 1 match in `reprocess_document` function (currently 0 — gap).

- [ ] **GRAPH-WORKER-04** — Worker writes `entity_count` and `relationship_count` surfaced via API — Phase: 10 — Status: Pending — Phase 14 (gap closure)
  - **Description:** Shares the same root cause as GRAPH-WORKER-01: the worker writes the counts to the document record, but `_doc_to_response` in `documents.py` omits them. Consumers cannot see how rich a document's graph build was.
  - **Definition of Done:**
    - `DocumentResponse` in `documents.py` includes `entity_count` and `relationship_count`.
    - `GET /v1/documents/{id}` returns non-null values when a build has completed.
  - **Verification criteria:**
    - `grep -n 'entity_count\|relationship_count' src/docingest/api/routes/documents.py` returns matches in `DocumentResponse` (currently absent — gap).

- [x] **GRAPH-WORKER-05** — `graph-worker` Docker service + spaCy model download — Phase: 10 — Status: Satisfied* (traceability added, VERIFICATION.md pending)
  - **Description:** Dedicated `graph-worker` Docker image and compose service. The Dockerfile (`python:3.12-slim` base) installs the project, downloads `en_core_web_lg` via `python -m spacy download`, and runs `arq docingest.workers.graph_builder.WorkerSettings`. The compose service depends on mongodb, redis, qdrant only (no minio), with 1 replica to keep RAM bounded (~500MB per spaCy process).
  - **Definition of Done:**
    - `docker/graph-worker.Dockerfile` exists with `python -m spacy download en_core_web_lg` and correct CMD.
    - `docker-compose.yml` has a `graph-worker` service pointing to the Dockerfile.
  - **Verification criteria:**
    - `grep -n "spacy download" docker/graph-worker.Dockerfile` returns 1 match.
    - `grep -n "graph_builder.WorkerSettings" docker/graph-worker.Dockerfile` returns 1 match.
    - `grep -n "graph-worker" docker-compose.yml` returns multiple matches.

## Community Detection (Phase 11)

- [ ] **COMM-01** — Leiden clustering over entity graph — Phase: 11 — Status: Partial — Phase 15 (fragile idx_to_entity invariant)
  - **Description:** `build_communities(db, tenant_id)` loads all tenant entities and relationships from MongoDB, builds an igraph via `_build_graph`, runs Leiden via `leidenalg.CPMVertexPartition` with per-level `resolution_parameter`, and filters singleton communities (size < 2). All blocking igraph/leidenalg calls are wrapped in `loop.run_in_executor`. Known fragility: `idx_to_entity` uses `enumerate(entities)` ordering, which implicitly assumes igraph vertex order equals list-insertion order — phase 15 will make this robust.
  - **Definition of Done:**
    - `build_communities` exported from `docingest.services.community_detection`.
    - Uses `leidenalg.CPMVertexPartition` (not `ModularityVertexPartition`).
    - Singleton communities (< 2 entities) are filtered.
    - `build_communities` uses `run_in_executor` for igraph and leidenalg calls.
  - **Verification criteria:**
    - `grep -n "def build_communities" src/docingest/services/community_detection.py` returns 1 match.
    - `grep -n "CPMVertexPartition" src/docingest/services/community_detection.py` returns at least 1 match.
    - `grep -n "run_in_executor" src/docingest/services/community_detection.py` returns multiple matches.

- [ ] **COMM-02** — Multi-resolution hierarchical community detection — Phase: 11 — Status: Partial — Phase 15 (same fragility as COMM-01)
  - **Description:** `_detect_communities_multi_resolution` iterates over the configured resolution list (default `[0.1, 0.5, 1.0]`), running Leiden at each level. Parent/child hierarchy is linked post-upsert by finding the coarser-level community with maximum entity_ids overlap. Same idx-ordering fragility as COMM-01.
  - **Definition of Done:**
    - `_detect_communities_multi_resolution` accepts a list of resolutions and returns per-level results.
    - `settings.community_resolutions` exists with default `[0.1, 0.5, 1.0]`.
    - Parent/child links are populated across levels after upserting all communities.
  - **Verification criteria:**
    - `grep -n "def _detect_communities_multi_resolution" src/docingest/services/community_detection.py` returns 1 match.
    - `python -c "from docingest.config import settings; assert settings.community_resolutions == [0.1, 0.5, 1.0]; print('OK')"` exits 0.
    - `grep -n "community_resolutions" src/docingest/config.py` returns 1 match.

- [ ] **COMM-03** — TF-IDF extractive summaries per community — Phase: 11 — Status: Partial — Phase 15 (missing ensure_collection guard in `_fetch_chunk_texts`)
  - **Description:** `_extractive_summary(texts, max_sentences)` uses `TfidfVectorizer(stop_words="english", max_features=5000)` to score sentences by mean TF-IDF, selects the top-k in original order, and joins them. `_fetch_chunk_texts(tenant_id, chunk_ids, batch_size)` scrolls Qdrant using a `HasIdCondition` filter in batches. Known fragility: `_fetch_chunk_texts` does not guard against a missing tenant collection (Qdrant throws on nonexistent collection) — phase 15 adds the guard.
  - **Definition of Done:**
    - `_extractive_summary` and `_fetch_chunk_texts` both exist in `community_detection.py`.
    - `settings.community_max_chunks` and `settings.community_max_summary_sentences` exist with defaults 50 and 5.
  - **Verification criteria:**
    - `grep -n "def _extractive_summary\|def _fetch_chunk_texts" src/docingest/services/community_detection.py` returns 2 matches.
    - `python -c "from docingest.config import settings; assert settings.community_max_chunks == 50; assert settings.community_max_summary_sentences == 5; print('OK')"` exits 0.

- [ ] **COMM-04** — Community embedding via FastEmbed — Phase: 11 — Status: Partial — Phase 15 (gap closure: asyncio deprecation)
  - **Description:** Community summaries are embedded by calling `embed_texts([summary])` via `loop.run_in_executor`; the vector is stored as `summary_embedding` on the community record using the same FastEmbed model used for chunk embeddings. Known fragility: `loop = asyncio.get_event_loop()` at line 52 uses the deprecated API (same issue as EE-08) — phase 15 migrates to `get_running_loop`.
  - **Definition of Done:**
    - `build_communities` uses `asyncio.get_running_loop()` not `get_event_loop()`.
  - **Verification criteria:**
    - `grep -n "embed_texts" src/docingest/services/community_detection.py` returns at least 1 match.
    - `grep -n "get_running_loop" src/docingest/services/community_detection.py` returns at least 1 match (currently 0 — gap).

- [x] **COMM-05** — `POST /v1/graph/communities/rebuild` API route — Phase: 11 — Status: Satisfied* (traceability added, VERIFICATION.md pending)
  - **Description:** `POST /v1/graph/communities/rebuild` endpoint authenticated via the `Tenant` dependency (API key + rate limiting). Returns HTTP 403 when `settings.graph_rag_enabled` is False. Calls `build_communities(db, tenant["tenant_id"])` and returns `{"status": "ok", "communities": stats}`. Structured logs for rebuild start and complete. Router mounted in `app.py` under `/v1`; `ensure_graph_indexes` wired into lifespan when graph is enabled.
  - **Definition of Done:**
    - `src/docingest/api/routes/graph.py` exists with `POST /communities/rebuild` endpoint.
    - Route returns HTTP 403 when `graph_rag_enabled=False`.
    - Router mounted in `app.py` under `/v1` prefix.
    - `ensure_graph_indexes` called in lifespan when `graph_rag_enabled=True`.
  - **Verification criteria:**
    - `grep -n "def rebuild_communities" src/docingest/api/routes/graph.py` returns 1 match.
    - `grep -n "graph.router" src/docingest/api/app.py` returns 1 match.
    - `grep -n "graph_rag_enabled" src/docingest/api/routes/graph.py` returns at least 1 match (the 403 gate).
    - `grep -n "ensure_graph_indexes" src/docingest/api/app.py` returns 1 match.

<!-- hr -->

*`Satisfied*` reflects that implementation is wired and functionally correct per the audit's integration checker, but lacks formal VERIFICATION.md traceability. Promote to `Satisfied` after `/gsd:verify-work` produces VERIFICATION.md for each phase.
