---
phase: 11-community-detection
plan: 01
subsystem: community-detection
tags: [graph-rag, leiden, community, tfidf, summarization]
dependency_graph:
  requires: [graph_store, embedding, qdrant, config]
  provides: [build_communities, community_detection_service]
  affects: [graph_store.upsert_community]
tech_stack:
  added: [python-igraph, leidenalg, scikit-learn]
  patterns: [multi-resolution-leiden, tfidf-extractive-summary, run-in-executor]
key_files:
  created:
    - src/docingest/services/community_detection.py
  modified:
    - pyproject.toml
    - src/docingest/config.py
decisions:
  - Used CPMVertexPartition for resolution-parameterized hierarchy (not ModularityVertexPartition)
  - Edge deduplication by (min,max) vertex pair with weight summing
  - Parent/child linking by maximum entity overlap across adjacent levels
  - ObjectId import from bson for clean MongoDB updates in hierarchy linking
metrics:
  duration: 4min
  completed: "2026-04-12T23:49:01Z"
  tasks: 2
  files: 3
---

# Phase 11 Plan 01: Community Detection Service Summary

Leiden multi-resolution community detection with TF-IDF extractive summaries and FastEmbed embedding, persisted via upsert_community

## What Was Built

### Task 1: Dependencies + Config (dc84e86)
- Added `python-igraph>=0.11,<2`, `leidenalg>=0.10,<1`, `scikit-learn>=1.5,<2` to pyproject.toml
- Added three community detection settings to config.py Settings class:
  - `community_resolutions: list[float] = [0.1, 0.5, 1.0]`
  - `community_max_chunks: int = 50`
  - `community_max_summary_sentences: int = 5`

### Task 2: Community Detection Service (d8a03a3)
Created `src/docingest/services/community_detection.py` (358 lines) with:

- **`build_communities(db, tenant_id, resolutions)`** -- Async orchestrator. Loads entities/relationships from MongoDB, builds igraph, runs Leiden at 3 resolutions, generates summaries, embeds them, upserts communities, links parent/child hierarchy.
- **`_build_graph(entities, relationships)`** -- Sync. Builds undirected igraph.Graph with vertex attributes. Deduplicates edges by (min,max) vertex pair, summing weights.
- **`_detect_communities_multi_resolution(graph, resolutions)`** -- Sync. Runs `leidenalg.find_partition` with `CPMVertexPartition` at each resolution. Returns {level: [[vertex_indices]]}.
- **`_extractive_summary(texts, max_sentences)`** -- Sync. Splits texts into sentences, scores by mean TF-IDF, returns top-k in original order.
- **`_generate_community_title(member_entities, level)`** -- Sync. Deterministic title from top-3 entities by mention_count: "L{level}: A, B, C".
- **`_fetch_chunk_texts(tenant_id, chunk_ids, batch_size)`** -- Async. Batch scroll from Qdrant using HasIdCondition filter.

All blocking calls (igraph, leidenalg, sklearn, embed_texts) use `loop.run_in_executor(None, ...)`.

## Decisions Made

1. **CPMVertexPartition over ModularityVertexPartition** -- CPM accepts resolution_parameter for multi-level hierarchy; Modularity produces only one "best" partition.
2. **Edge dedup by (min, max) pair** -- Ensures undirected edge uniqueness regardless of relationship direction, with weights summed.
3. **Parent/child by max overlap** -- Post-upsert, each finer-level community finds the coarser-level community sharing the most entity_ids. Simple and correct for 3-level hierarchies.
4. **Singleton filtering (size < 2)** -- Communities with a single entity add noise; filtered before summary generation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff B905 lint error for zip() without strict=**
- Found during: Task 2 verification
- Issue: `zip(*[(k, v) ...])` missing `strict=True` parameter
- Fix: Added `strict=True` to zip call
- Files modified: src/docingest/services/community_detection.py

**2. [Rule 1 - Bug] Fixed import ordering (ruff I001)**
- Found during: Task 2 verification
- Issue: bson import in separate block from other third-party imports
- Fix: `ruff check --fix` auto-sorted imports
- Files modified: src/docingest/services/community_detection.py

## Known Stubs

None -- all functions are fully implemented with real logic.

## Verification Results

- Syntax check: PASSED
- Ruff lint: PASSED (0 errors)
- All 6 functions present: PASSED
- build_communities is async: PASSED
- pyproject.toml has all 3 deps: PASSED
- config.py has all 3 settings: PASSED
- Min lines (150): PASSED (358 lines)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | dc84e86 | chore(11-01): add community detection dependencies and config settings |
| 2 | d8a03a3 | feat(11-01): create community detection service with Leiden algorithm |

## Self-Check: PASSED

All 3 files found. Both commits verified.
