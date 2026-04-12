---
phase: 09-entity-extraction
plan: 01
subsystem: nlp
tags: [spacy, ner, svo, dependency-parse, fuzzy-match, difflib, entity-extraction]

# Dependency graph
requires:
  - phase: 08-graph-data-models
    provides: EntityType enum, Entity/Relationship Pydantic models
provides:
  - extract_entities() NER extraction with spaCy
  - extract_relationships() SVO dependency parse extraction
  - resolve_entity() fuzzy entity deduplication via difflib
  - Async wrappers for CPU-bound offloading
affects: [09-02, graph-rag-pipeline, knowledge-graph-construction]

# Tech tracking
tech-stack:
  added: ["spacy>=3.7,<4", "en_core_web_sm (test)"]
  patterns: [lazy-load-singleton-with-lock, spacy-label-mapping, svo-dependency-traversal]

key-files:
  created:
    - src/docingest/services/entity_extraction.py
    - tests/test_entity_extraction.py
  modified:
    - pyproject.toml

key-decisions:
  - "Followed embedding.py lazy-load + threading.Lock pattern exactly for spaCy model singleton"
  - "Filter out EntityType.OTHER entities by default to reduce graph noise"
  - "SVO extraction requires BOTH source and target in entity list (strict filtering)"
  - "Used difflib.SequenceMatcher (stdlib) for fuzzy matching instead of adding rapidfuzz dependency"

patterns-established:
  - "spaCy label mapping: dict-based with OTHER fallback for unknown labels"
  - "SVO extraction: VERB token traversal with nsubj/nsubjpass + dobj/attr/pobj expansion"
  - "Entity dedup: SequenceMatcher ratio + entity_type match requirement"

requirements-completed: [EE-01, EE-02, EE-03, EE-04, EE-05, EE-06, EE-07, EE-08]

# Metrics
duration: 5min
completed: 2026-04-12
---

# Phase 9 Plan 1: Entity & Relationship Extraction Service Summary

**spaCy NER entity extraction with SVO dependency-parse relationships and difflib fuzzy deduplication, following embedding.py singleton pattern**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-12T23:26:37Z
- **Completed:** 2026-04-12T23:31:12Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created entity_extraction.py service with 6 public functions + 3 private helpers matching embedding.py pattern
- All 18 spaCy NER labels mapped to 8 EntityType enum values with OTHER filtering
- SVO relationship extraction via dependency tree traversal with compound modifier expansion
- Fuzzy entity deduplication using difflib.SequenceMatcher with configurable threshold and type enforcement
- 36 comprehensive tests all passing (pure logic + model-dependent with en_core_web_sm)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add spaCy dependency and create entity_extraction.py** - `40570c5` (feat)
2. **Task 2: Create comprehensive unit tests** - `43d9500` (test)

## Files Created/Modified
- `pyproject.toml` - Added spacy>=3.7,<4 dependency
- `src/docingest/services/entity_extraction.py` - NER extraction, SVO parsing, fuzzy dedup (224 lines)
- `tests/test_entity_extraction.py` - 36 tests covering all requirements (248 lines)

## Decisions Made
- Followed embedding.py lazy-load + threading.Lock pattern exactly for consistency
- Filter out EntityType.OTHER by default (CARDINAL, ORDINAL, MONEY, PERCENT, QUANTITY are noise for knowledge graphs)
- Require BOTH source and target to be known entities for SVO triples (strict filtering reduces noise)
- Used stdlib difflib.SequenceMatcher instead of adding rapidfuzz dependency
- Used dict keys source/target/relation_type/description per plan spec

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff lint errors in test file**
- **Found during:** Task 2
- **Issue:** E402 (imports after importorskip) and F841 (unused variable) lint violations
- **Fix:** Added noqa comments for E402, removed unused sync_result variable, ran ruff --fix for import sorting
- **Files modified:** tests/test_entity_extraction.py
- **Verification:** ruff check passes clean

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Minor lint cleanup. No scope creep.

## Issues Encountered
None.

## Known Stubs
None - all functions fully implemented with real spaCy model calls.

## User Setup Required
None - no external service configuration required. spaCy model download is automated via `python -m spacy download en_core_web_sm` for testing. Production uses en_core_web_lg (configured via SPACY_MODEL env var).

## Next Phase Readiness
- Entity extraction service ready for integration into graph RAG pipeline
- extract_entities + extract_relationships can be called from chunker worker or dedicated graph worker
- resolve_entity ready for entity deduplication during graph construction
- Async wrappers available for non-blocking pipeline integration

---
*Phase: 09-entity-extraction*
*Completed: 2026-04-12*
