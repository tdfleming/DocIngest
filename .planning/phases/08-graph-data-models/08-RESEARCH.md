# Phase 8: Data Models & Graph DB Layer - Research

**Researched:** 2026-04-12
**Domain:** Pydantic v2 models + MongoDB (Motor async) persistence for knowledge graph
**Confidence:** HIGH

## Summary

This phase adds three Pydantic models (Entity, Relationship, Community) and a MongoDB persistence layer (graph_store.py) to support Graph RAG. The codebase has clean, well-established patterns: StrEnum for enums, Pydantic BaseModel with `Field(default_factory=...)` for timestamps, Motor async driver with module-level `_client`/`_db` singletons, and `ensure_indexes` for index creation.

The key technical decisions are: (1) use `$graphLookup` aggregation for neighbor traversal (fully supported in MongoDB 7 + Motor 3.7), (2) do NOT use `$vectorSearch` for community embedding search (requires MongoDB 8.2+ with `mongot` binary -- project runs MongoDB 7), instead compute cosine similarity in Python or store community embeddings in Qdrant alongside chunk vectors, (3) use `$pull` for cleaning doc references from entities/relationships during reprocessing.

**Primary recommendation:** Follow existing patterns exactly. Models in `models/graph.py` with StrEnum + BaseModel. DB operations in `db/graph_store.py` as standalone async functions taking `db: AsyncIOMotorDatabase`. For community embedding search, use Python-side cosine similarity (community count per tenant will be small, typically < 1000) or delegate to Qdrant.

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 | Data models | Already used for Document, User models |
| motor | 3.7.1 | Async MongoDB driver | Already used in db/mongodb.py |
| pymongo (via motor) | 4.x | MongoDB operations (motor wraps pymongo) | Provides aggregation pipeline support including $graphLookup |

### No New Dependencies Required
This phase requires zero new pip packages. All functionality is covered by existing motor/pydantic stack.

## Architecture Patterns

### Project Structure (additions only)
```
src/docingest/
├── models/
│   ├── document.py      # existing
│   ├── user.py          # existing
│   └── graph.py         # NEW: Entity, Relationship, Community models
├── db/
│   ├── mongodb.py       # MODIFIED: call ensure_graph_indexes
│   └── graph_store.py   # NEW: all graph CRUD operations
└── config.py            # MODIFIED: add graph_rag settings
```

### Pattern 1: Pydantic Model with StrEnum (from existing codebase)
**What:** StrEnum for categorical fields, BaseModel with Field defaults, `model_config = {"populate_by_name": True}` for MongoDB `_id` alias.
**When to use:** Every model that gets stored in MongoDB.
**Example (from document.py lines 7-60):**
```python
from enum import StrEnum
from datetime import UTC, datetime
from pydantic import BaseModel, Field

class EntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    # ... etc

class Entity(BaseModel):
    id: str = Field(default="", alias="_id")
    tenant_id: str
    name: str
    entity_type: EntityType
    # ... fields ...
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"populate_by_name": True}
```

### Pattern 2: MongoDB Operations as Module Functions (from existing codebase)
**What:** Standalone async functions taking `db: AsyncIOMotorDatabase` as first param. No class wrappers.
**When to use:** All DB operations.
**Example (from mongodb.py lines 48-72):**
```python
async def insert_document(db: AsyncIOMotorDatabase, doc: dict[str, Any]) -> str:
    doc["created_at"] = datetime.now(UTC)
    doc["updated_at"] = datetime.now(UTC)
    result = await db.documents.insert_one(doc)
    return str(result.inserted_id)

async def update_document_status(
    db: AsyncIOMotorDatabase,
    doc_id: str,
    status: DocumentStatus,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    update: dict[str, Any] = {"$set": {"status": status, "updated_at": datetime.now(UTC)}}
    if extra_fields:
        update["$set"].update(extra_fields)
    await db.documents.update_one({"_id": ObjectId(doc_id)}, update)
```

### Pattern 3: Index Creation in ensure_indexes (from existing codebase)
**What:** All indexes declared in a single `ensure_indexes` function, called at app startup.
**When to use:** Adding new collection indexes.
**Example (from mongodb.py lines 30-42):**
```python
async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.documents.create_index([("tenant_id", 1), ("source_hash", 1)])
    # ... more indexes
```

### Pattern 4: Config via pydantic-settings (from existing codebase)
**What:** Fields on the `Settings` class with defaults, loaded from env vars.
**Example (from config.py):**
```python
class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}
    # New fields just go inline with the rest:
    graph_rag_enabled: bool = False
    spacy_model: str = "en_core_web_lg"
    entity_confidence_threshold: float = 0.7
    max_entities_per_chunk: int = 50
```

### Anti-Patterns to Avoid
- **Class-based DB layer:** The codebase uses module-level functions, not repository classes. Do not introduce a `GraphStore` class.
- **ObjectId for graph entity IDs:** The existing Document model uses `str` for IDs (`Field(default="", alias="_id")`). Graph entities should use the same pattern, generating string IDs (e.g., UUID4 hex or letting MongoDB generate ObjectId and converting to str).
- **Sync MongoDB calls:** Everything is async via Motor. Never use pymongo directly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph traversal | Manual recursive queries | MongoDB `$graphLookup` | Built-in, handles cycles, depth limiting, tenant filtering via `restrictSearchWithMatch` |
| Upsert with dedup | find-then-insert logic | `update_one` with `upsert=True` | Atomic, race-condition-free |
| Cosine similarity (for community search) | NumPy dot product loops | `numpy.dot` / `scipy.spatial.distance.cosine` or Qdrant collection | For small sets (<1000 communities), Python is fine; for scale, use Qdrant |
| Batch operations | Sequential loops | `asyncio.gather` for independent ops, `bulk_write` for batch MongoDB ops | Existing codebase pattern (see CLAUDE.md: "Use asyncio.gather for independent async operations") |

**Key insight:** MongoDB `$graphLookup` eliminates the need for a dedicated graph database. It handles recursive traversal within a single aggregation pipeline, with tenant isolation via `restrictSearchWithMatch`.

## Common Pitfalls

### Pitfall 1: $graphLookup Memory Limit
**What goes wrong:** `$graphLookup` results are subject to the 16MB BSON document size limit. A highly connected entity could exceed this.
**Why it happens:** All traversed documents are accumulated into a single array field in the output document.
**How to avoid:** Always set `maxDepth` (use 1 for neighbors, max 2 for extended graph). Use `restrictSearchWithMatch` to filter by `tenant_id` to limit the search scope.
**Warning signs:** Aggregation errors mentioning document size limits.

### Pitfall 2: Missing Compound Indexes for Upsert Dedup
**What goes wrong:** Upsert operations are slow or create duplicates.
**Why it happens:** Without a unique compound index on the dedup fields, `update_one(upsert=True)` may not match existing docs efficiently.
**How to avoid:** Create compound indexes: `(tenant_id, name, entity_type)` for entities, `(tenant_id, source_entity_id, target_entity_id, relation_type)` for relationships. Make these unique.
**Warning signs:** Duplicate entities appearing in queries.

### Pitfall 3: $vectorSearch Not Available on MongoDB 7
**What goes wrong:** Attempting to use `$vectorSearch` aggregation stage fails.
**Why it happens:** `$vectorSearch` requires MongoDB 8.2+ with the `mongot` companion binary. The project runs `mongo:7`.
**How to avoid:** For `search_communities`, either: (a) fetch all communities for the tenant and compute cosine similarity in Python (viable for < 1000 communities), or (b) store community embeddings in a Qdrant collection and search there.
**Warning signs:** Aggregation pipeline error "Unrecognized pipeline stage name: '$vectorSearch'".

### Pitfall 4: Forgetting to Clean Graph Data on Document Reprocessing
**What goes wrong:** Stale entities and relationships accumulate when a document is reprocessed or deleted.
**Why it happens:** Graph entities reference doc_ids in arrays. Simply deleting the document doesn't clean up graph references.
**How to avoid:** `delete_doc_graph_data` must: (1) `$pull` the doc_id from `doc_ids` arrays on entities and relationships, (2) delete entities/relationships where `doc_ids` becomes empty after the pull, (3) update `mention_count` on entities.
**Warning signs:** Entity mention counts that only go up, never down.

### Pitfall 5: Not Using Pydantic model_dump for MongoDB Insert
**What goes wrong:** Pydantic model serialization issues with enums, datetimes.
**Why it happens:** Passing model objects directly to Motor instead of dicts.
**How to avoid:** Use `entity.model_dump(by_alias=True, exclude_unset=True)` before inserting. The existing pattern in the codebase passes plain dicts to MongoDB operations (see `insert_document` which takes `dict[str, Any]`).
**Warning signs:** TypeError or serialization errors on insert.

## Code Examples

### Entity Upsert with Dedup
```python
# Upsert entity: dedup by (name, type, tenant), merge doc_ids and chunk_ids
async def upsert_entity(
    db: AsyncIOMotorDatabase, tenant_id: str, entity: dict[str, Any]
) -> str:
    now = datetime.now(UTC)
    result = await db.entities.update_one(
        {
            "tenant_id": tenant_id,
            "name": entity["name"],
            "entity_type": entity["entity_type"],
        },
        {
            "$set": {
                "updated_at": now,
                "embedding": entity.get("embedding"),
                "metadata": entity.get("metadata", {}),
            },
            "$addToSet": {
                "doc_ids": {"$each": entity.get("doc_ids", [])},
                "chunk_ids": {"$each": entity.get("chunk_ids", [])},
                "aliases": {"$each": entity.get("aliases", [])},
            },
            "$inc": {"mention_count": entity.get("mention_count", 1)},
            "$setOnInsert": {
                "tenant_id": tenant_id,
                "name": entity["name"],
                "entity_type": entity["entity_type"],
                "created_at": now,
            },
        },
        upsert=True,
    )
    if result.upserted_id:
        return str(result.upserted_id)
    # Return existing doc id
    existing = await db.entities.find_one(
        {"tenant_id": tenant_id, "name": entity["name"], "entity_type": entity["entity_type"]},
        {"_id": 1},
    )
    return str(existing["_id"]) if existing else ""
```

### $graphLookup for Neighbor Traversal
```python
# Get entity neighbors up to max_hops
async def get_entity_neighbors(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    entity_id: str,
    max_hops: int = 1,
) -> list[dict]:
    pipeline = [
        {"$match": {"_id": ObjectId(entity_id), "tenant_id": tenant_id}},
        {
            "$graphLookup": {
                "from": "relationships",
                "startWith": "$_id",
                "connectFromField": "target_entity_id",
                "connectToField": "source_entity_id",
                "as": "connections",
                "maxDepth": max_hops - 1,  # 0-indexed depth
                "depthField": "hop",
                "restrictSearchWithMatch": {"tenant_id": tenant_id},
            }
        },
    ]
    result = await db.entities.aggregate(pipeline).to_list(length=1)
    if not result:
        return []
    return result[0].get("connections", [])
```

**Note on $graphLookup approach:** The above is one approach. An alternative (and potentially simpler) approach is a two-step query: (1) find all relationships where `source_entity_id == entity_id` or `target_entity_id == entity_id`, (2) fetch the connected entity docs. For `max_hops=1` (the default), this avoids the complexity of `$graphLookup` and is easier to reason about. For `max_hops > 1`, `$graphLookup` is the right choice.

### Simpler Neighbor Query (for max_hops=1)
```python
async def get_entity_neighbors(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    entity_id: str,
    max_hops: int = 1,
) -> list[dict]:
    eid = ObjectId(entity_id)
    # Step 1: Find relationships involving this entity
    rels = await db.relationships.find({
        "tenant_id": tenant_id,
        "$or": [
            {"source_entity_id": str(eid)},
            {"target_entity_id": str(eid)},
        ],
    }).to_list(length=500)

    # Step 2: Collect neighbor entity IDs
    neighbor_ids = set()
    for r in rels:
        if r["source_entity_id"] != str(eid):
            neighbor_ids.add(r["source_entity_id"])
        if r["target_entity_id"] != str(eid):
            neighbor_ids.add(r["target_entity_id"])

    if not neighbor_ids:
        return []

    # Step 3: Fetch neighbor entities
    neighbors = await db.entities.find({
        "_id": {"$in": [ObjectId(nid) for nid in neighbor_ids]},
        "tenant_id": tenant_id,
    }).to_list(length=500)

    if max_hops == 1:
        return neighbors

    # For max_hops > 1: recurse or use $graphLookup
    # ... (implement if needed)
    return neighbors
```

### Community Embedding Search (Python-side cosine)
```python
import numpy as np

async def search_communities(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    query_embedding: list[float],
    limit: int = 5,
) -> list[dict]:
    # Fetch all communities for this tenant (small dataset)
    communities = await db.communities.find(
        {"tenant_id": tenant_id, "summary_embedding": {"$exists": True}},
    ).to_list(length=None)

    if not communities:
        return []

    # Compute cosine similarity
    query_vec = np.array(query_embedding)
    scored = []
    for comm in communities:
        emb = np.array(comm["summary_embedding"])
        similarity = float(np.dot(query_vec, emb) / (np.linalg.norm(query_vec) * np.linalg.norm(emb) + 1e-10))
        scored.append((similarity, comm))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [comm for _, comm in scored[:limit]]
```

**Note:** numpy is already an indirect dependency (fastembed depends on it). No new install needed.

### Delete Doc Graph Data (Cleanup)
```python
async def delete_doc_graph_data(
    db: AsyncIOMotorDatabase, tenant_id: str, doc_id: str
) -> None:
    # Pull doc_id from all entities and relationships
    await asyncio.gather(
        db.entities.update_many(
            {"tenant_id": tenant_id, "doc_ids": doc_id},
            {"$pull": {"doc_ids": doc_id, "chunk_ids": {"$regex": f"^{doc_id}:"}}, "$inc": {"mention_count": -1}},
        ),
        db.relationships.update_many(
            {"tenant_id": tenant_id, "doc_ids": doc_id},
            {"$pull": {"doc_ids": doc_id, "chunk_ids": {"$regex": f"^{doc_id}:"}}},
        ),
    )
    # Remove entities/relationships with no remaining doc references
    await asyncio.gather(
        db.entities.delete_many({"tenant_id": tenant_id, "doc_ids": {"$size": 0}}),
        db.relationships.delete_many({"tenant_id": tenant_id, "doc_ids": {"$size": 0}}),
    )
```

### Index Creation
```python
async def ensure_graph_indexes(db: AsyncIOMotorDatabase) -> None:
    # Entities: unique dedup index + lookup indexes
    await db.entities.create_index(
        [("tenant_id", 1), ("name", 1), ("entity_type", 1)],
        unique=True,
    )
    await db.entities.create_index([("tenant_id", 1), ("doc_ids", 1)])
    await db.entities.create_index([("tenant_id", 1), ("entity_type", 1)])

    # Relationships: unique dedup index + lookup indexes
    await db.relationships.create_index(
        [("tenant_id", 1), ("source_entity_id", 1), ("target_entity_id", 1), ("relation_type", 1)],
        unique=True,
    )
    await db.relationships.create_index([("tenant_id", 1), ("source_entity_id", 1)])
    await db.relationships.create_index([("tenant_id", 1), ("target_entity_id", 1)])
    await db.relationships.create_index([("tenant_id", 1), ("doc_ids", 1)])

    # Communities: lookup indexes
    await db.communities.create_index([("tenant_id", 1), ("level", 1)])
    await db.communities.create_index([("tenant_id", 1), ("entity_ids", 1)])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Neo4j/dedicated graph DB for knowledge graphs | MongoDB $graphLookup for modest graph needs | MongoDB 3.4+ (2017), but widely adopted for Graph RAG 2024-2025 | No extra infrastructure needed |
| $vectorSearch only on Atlas | $vectorSearch on Community Edition | MongoDB 8.2 (Sep 2025, preview) | Not yet usable in production; project on MongoDB 7 |
| Pydantic v1 model schemas | Pydantic v2 with model_config dict | Pydantic 2.0 (2023) | Project already on v2; use model_config not Config class |

## Open Questions

1. **Entity ID format: ObjectId string vs UUID4?**
   - What we know: Document model uses MongoDB ObjectId converted to string via `alias="_id"`. Graph entities reference each other by ID in relationship source/target fields.
   - What's unclear: Whether string ObjectIds or UUID4 hex strings are better for cross-referencing between entities and relationships.
   - Recommendation: Use MongoDB ObjectId (same as Document model) for consistency. Store as string in relationship foreign key fields. This is the existing pattern.

2. **Community embedding search: Python cosine vs Qdrant collection?**
   - What we know: MongoDB 7 lacks $vectorSearch. Community count per tenant is typically small (< 1000). Qdrant is already deployed.
   - What's unclear: Whether a separate Qdrant collection for communities is overkill at this stage.
   - Recommendation: Start with Python-side cosine similarity using numpy (already available as transitive dep). Add Qdrant collection later if community counts grow large. Keep the function signature compatible with either approach.

3. **Neighbor traversal: $graphLookup vs two-step query?**
   - What we know: For max_hops=1 (the default and most common case), a simple two-step query (find relationships, then fetch entities) is clearer and easier to test. $graphLookup shines at max_hops >= 2.
   - Recommendation: Implement the simple two-step approach for max_hops=1, with $graphLookup as the fallback for multi-hop. This can be a single function with an if-branch.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.25.x |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-01 | Entity model validates fields, enums, defaults | unit | `pytest tests/test_graph_models.py -x` | No - Wave 0 |
| GRAPH-02 | Relationship model validates fields and defaults | unit | `pytest tests/test_graph_models.py -x` | No - Wave 0 |
| GRAPH-03 | Community model validates fields and defaults | unit | `pytest tests/test_graph_models.py -x` | No - Wave 0 |
| GRAPH-04 | upsert_entity deduplicates by (name, type, tenant) | integration | `pytest tests/test_graph_store.py::test_upsert_entity -x` | No - Wave 0 |
| GRAPH-05 | get_entity_neighbors returns connected entities | integration | `pytest tests/test_graph_store.py::test_neighbors -x` | No - Wave 0 |
| GRAPH-06 | delete_doc_graph_data cleans up references | integration | `pytest tests/test_graph_store.py::test_cleanup -x` | No - Wave 0 |
| GRAPH-07 | Config fields have correct defaults | unit | `pytest tests/test_graph_models.py::test_config -x` | No - Wave 0 |

### Wave 0 Gaps
- [ ] `tests/test_graph_models.py` -- covers GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-07
- [ ] `tests/test_graph_store.py` -- covers GRAPH-04, GRAPH-05, GRAPH-06 (requires MongoDB test fixture)

## Sources

### Primary (HIGH confidence)
- Codebase files: `src/docingest/models/document.py`, `src/docingest/db/mongodb.py`, `src/docingest/db/qdrant.py`, `src/docingest/config.py` -- actual patterns in use
- `docker-compose.yml` -- confirms MongoDB 7, Motor 3.7.1, Pydantic 2.12.5
- [MongoDB $graphLookup official docs](https://www.mongodb.com/docs/manual/reference/operator/aggregation/graphlookup/) -- syntax, parameters, limitations

### Secondary (MEDIUM confidence)
- [MongoDB Community Edition Vector Search announcement](https://www.mongodb.com/company/blog/product-release-announcements/supercharge-self-managed-apps-search-vector-search-capabilities) -- confirms $vectorSearch requires MongoDB 8.2+
- [MongoDB $graphLookup blog post (2026)](https://oneuptime.com/blog/post/2026-01-30-mongodb-graph-lookups/view) -- practical patterns

### Tertiary (LOW confidence)
- Community embedding search approach (Python cosine) -- standard practice but not verified against a specific Graph RAG implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all patterns from existing codebase
- Architecture: HIGH -- follows existing module-function pattern exactly
- Pitfalls: HIGH -- $vectorSearch limitation confirmed via MongoDB version check, $graphLookup constraints from official docs
- Community search approach: MEDIUM -- Python cosine is straightforward but may need Qdrant later

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable domain, no fast-moving dependencies)
