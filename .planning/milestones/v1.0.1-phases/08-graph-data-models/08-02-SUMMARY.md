---
phase: 08-graph-data-models
plan: 02
subsystem: database
tags: [mongodb, graph-rag, crud, knowledge-graph, async]

requires: [08-01]
provides:
  - 12 async CRUD functions for graph entities, relationships, and communities
  - Atomic upsert with dedup for entities and relationships
  - Multi-hop neighbor traversal via two-step query and $graphLookup
  - Python cosine similarity for community embedding search
  - Document graph data cleanup with orphan removal
affects: [08-03, graph-extraction, graph-search, document-deletion]

tech-stack:
  added: []
  patterns: [atomic upsert with $addToSet/$inc, two-step neighbor query for 1-hop, $graphLookup for multi-hop, Python-side cosine similarity with numpy]

key-files:
  created:
    - src/docingest/db/graph_store.py
    - tests/test_graph_store.py
  modified:
    - src/docingest/db/mongodb.py

key-decisions:
  - "Used two-step query for 1-hop neighbors (simpler, testable) and $graphLookup for multi-hop"
  - "Python-side cosine similarity with numpy for community search (no $vectorSearch on MongoDB 7)"
  - "Conditional graph index creation gated by settings.graph_rag_enabled"

patterns-established:
  - "Graph CRUD follows exact mongodb.py pattern: module-level async functions with db param"
  - "Upsert dedup via unique compound indexes + update_one(upsert=True)"

requirements-completed: [GRAPH-04, GRAPH-05, GRAPH-06]

duration: 6min
completed: 2026-04-12
---

# Phase 08 Plan 02: Graph Store CRUD Operations Summary

**12 async MongoDB CRUD functions for graph entities, relationships, and communities with atomic upsert dedup, neighbor traversal, and document cleanup**

## What Was Built

- **ensure_graph_indexes** - unique compound indexes for entity/relationship dedup, plus lookup indexes for communities
- **upsert_entity** - atomic upsert by (tenant_id, name, entity_type) with $addToSet for doc_ids/chunk_ids/aliases and $inc for mention_count
- **upsert_relationship** - atomic upsert by (tenant_id, source, target, relation_type) with $addToSet for doc_ids/chunk_ids
- **get_entity_by_id** - find_one by ObjectId, returns dict or None
- **find_entities_by_names** - batch lookup by tenant + name list
- **get_entity_neighbors** - two-step query for 1-hop (find relationships, fetch entities), $graphLookup for multi-hop
- **list_entities** - paginated query with optional entity_type filter, returns (docs, total) tuple
- **upsert_community** - upsert by (tenant_id, level, title) with $set for remaining fields
- **get_communities_by_level** - find by tenant + level
- **search_communities_by_embedding** - fetch all tenant communities, rank by cosine similarity using numpy
- **delete_doc_graph_data** - $pull doc_id from arrays, $inc mention_count by -1, delete orphans with empty doc_ids
- **get_graph_stats** - concurrent count_documents on entities, relationships, communities via asyncio.gather
- **mongodb.py wiring** - ensure_indexes conditionally calls ensure_graph_indexes when graph_rag_enabled is True

## TDD Execution

| Phase    | Tests | Result |
|----------|-------|--------|
| RED      | 15    | FAIL (ModuleNotFoundError - expected) |
| GREEN    | 15    | PASS |
| REFACTOR | 15    | PASS (ruff fixed unused asyncio import in tests) |

## Commits

| Hash      | Type | Description |
|-----------|------|-------------|
| 4808348   | test | Add failing tests for graph store CRUD operations |
| 599884e   | feat | Implement graph store CRUD operations |
| c8ed36b   | feat | Wire graph indexes into ensure_indexes |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all 12 functions are fully implemented with correct MongoDB operations, tenant scoping, and dedup logic.

## Self-Check: PASSED
