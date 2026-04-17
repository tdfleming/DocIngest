---
phase: 08-graph-data-models
plans: 2
waves: 2
---

# Phase 8: Data Models & Graph DB Layer

## Overview

Create Pydantic models and MongoDB persistence layer for entities, relationships, and communities that form the knowledge graph.

## Plan Structure

| Plan | Wave | Objective | Tasks | Autonomous | Depends On |
|------|------|-----------|-------|------------|------------|
| 08-01 | 1 | Pydantic models (Entity, Relationship, Community) + config fields | 1 (TDD) | yes | none |
| 08-02 | 2 | graph_store.py CRUD operations + mongodb.py wiring | 2 (TDD + wiring) | yes | 08-01 |

## Wave Execution

**Wave 1:** 08-01-PLAN.md -- Models and config (TDD)
**Wave 2:** 08-02-PLAN.md -- DB persistence layer (TDD + wiring)

## Files Modified

| File | Plan |
|------|------|
| src/docingest/models/graph.py | 08-01 |
| src/docingest/config.py | 08-01 |
| tests/test_graph_models.py | 08-01 |
| src/docingest/db/graph_store.py | 08-02 |
| src/docingest/db/mongodb.py | 08-02 |
| tests/test_graph_store.py | 08-02 |

## Requirements Coverage

| Requirement | Plan |
|-------------|------|
| GRAPH-01 (Entity model) | 08-01 |
| GRAPH-02 (Relationship model) | 08-01 |
| GRAPH-03 (Community model) | 08-01 |
| GRAPH-04 (upsert_entity dedup) | 08-02 |
| GRAPH-05 (get_entity_neighbors) | 08-02 |
| GRAPH-06 (delete_doc_graph_data cleanup) | 08-02 |
| GRAPH-07 (Config defaults) | 08-01 |
