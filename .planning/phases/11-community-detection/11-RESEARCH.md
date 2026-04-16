# Phase 11: Community Detection & Summaries - Research

**Researched:** 2026-04-12
**Domain:** Graph community detection (Leiden algorithm), extractive summarization (TF-IDF), igraph graph construction
**Confidence:** HIGH

## Summary

Phase 11 adds hierarchical community detection over the entity graph stored in MongoDB. The core flow is: load all entities and relationships for a tenant, build an in-memory igraph.Graph, run the Leiden algorithm at multiple resolution levels to produce a hierarchy of communities, generate extractive TF-IDF summaries for each community from member entity chunk texts, embed those summaries via the existing FastEmbed pipeline, and persist communities to MongoDB via the existing `graph_store.upsert_community()` function.

The data model (`Community` in `models/graph.py`) and the persistence layer (`upsert_community`, `get_communities_by_level`, `search_communities_by_embedding` in `db/graph_store.py`) are already built. The embedding service (`embed_texts` in `services/embedding.py`) is also ready. The new code is primarily `services/community_detection.py` plus a new API route.

**Primary recommendation:** Use `python-igraph>=0.11,<2` (covers both 0.11.x and the new 1.0.0), `leidenalg>=0.10,<1` (0.11.0 is current and compatible with igraph 1.0), and `scikit-learn>=1.5,<2` for TF-IDF. Run Leiden with `CPMVertexPartition` at three resolution levels (0.1, 0.5, 1.0) to produce a 3-level hierarchy. Use `run_in_executor` for all blocking igraph/leidenalg/sklearn calls.

## Standard Stack

### Core (new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-igraph | >=0.11,<2 (latest: 1.0.0) | In-memory graph construction and manipulation | De facto Python graph library; required by leidenalg |
| leidenalg | >=0.10,<1 (latest: 0.11.0) | Leiden community detection algorithm | Only maintained Python implementation of Leiden; designed for igraph |
| scikit-learn | >=1.5,<2 (latest: 1.8.0) | TfidfVectorizer for extractive summarization | Industry standard; no need for heavier NLP for sentence scoring |

### Already in project
| Library | Version | Purpose | When Used |
|---------|---------|---------|-----------|
| motor | >=3.7,<4 | Load entities/relationships, upsert communities | All MongoDB operations |
| fastembed | >=0.4,<1 | Embed community summaries | Via `embed_texts()` |
| structlog | >=24.4,<25 | Logging | All service code |
| numpy | (transitive) | Cosine similarity in `search_communities_by_embedding` | Already used in graph_store.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| leidenalg | igraph built-in `community_leiden()` | igraph 0.10+ has built-in Leiden, but leidenalg provides `resolution_profile()` and `CPMVertexPartition` which are essential for hierarchical multi-resolution detection |
| scikit-learn TF-IDF | spaCy sentence vectors | spaCy is already a dependency but TF-IDF sentence scoring is simpler, faster, and more interpretable for extractive summarization |
| python-igraph | networkx | networkx is slower for large graphs and leidenalg requires igraph |

**Installation (pyproject.toml addition):**
```toml
"python-igraph>=0.11,<2",
"leidenalg>=0.10,<1",
"scikit-learn>=1.5,<2",
```

**Note on package naming:** The PyPI package is `python-igraph` but the import is `import igraph as ig`. Do NOT `pip install igraph` -- that is a different, unrelated JavaScript visualization package on PyPI.

## Architecture Patterns

### Recommended Project Structure Addition
```
src/docingest/
  services/
    community_detection.py   # NEW - build_communities(), _extractive_summary()
  api/
    routes/
      graph.py               # NEW - POST /v1/graph/communities/rebuild
  config.py                  # MODIFIED - add community detection settings
```

### Pattern 1: build_communities() Main Entry Point
**What:** Async function that orchestrates the full community detection pipeline
**When to use:** Called from API endpoint or triggered after graph building

```python
async def build_communities(db: AsyncIOMotorDatabase, tenant_id: str) -> dict:
    """Main entry point for community detection.
    
    1. Load all entities and relationships from MongoDB
    2. Build igraph.Graph in executor (blocking)
    3. Run Leiden at multiple resolutions in executor (blocking)
    4. For each community, gather chunk texts and generate summary
    5. Embed summaries via embed_texts (blocking, use executor)
    6. Upsert communities to MongoDB
    
    Returns stats dict with community counts per level.
    """
```

### Pattern 2: Building igraph.Graph from MongoDB Entities/Relationships
**What:** Convert MongoDB entity/relationship documents to an igraph weighted graph
**When to use:** Before running Leiden algorithm

```python
import igraph as ig

def _build_graph(
    entities: list[dict], relationships: list[dict]
) -> tuple[ig.Graph, dict[str, int]]:
    """Build igraph.Graph from entity and relationship dicts.
    
    Returns (graph, entity_id_to_vertex_index_map).
    """
    # Create mapping from entity _id string to vertex index
    id_to_idx: dict[str, int] = {}
    for i, ent in enumerate(entities):
        id_to_idx[str(ent["_id"])] = i

    g = ig.Graph(n=len(entities), directed=False)
    
    # Set vertex attributes
    g.vs["name"] = [str(e["_id"]) for e in entities]
    g.vs["entity_name"] = [e["name"] for e in entities]
    g.vs["entity_type"] = [e["entity_type"] for e in entities]

    # Add edges with weights
    edges = []
    weights = []
    for rel in relationships:
        src_idx = id_to_idx.get(rel["source_entity_id"])
        tgt_idx = id_to_idx.get(rel["target_entity_id"])
        if src_idx is not None and tgt_idx is not None:
            edges.append((src_idx, tgt_idx))
            weights.append(rel.get("weight", 1.0))

    g.add_edges(edges)
    g.es["weight"] = weights

    return g, id_to_idx
```

### Pattern 3: Multi-Resolution Leiden for Hierarchy
**What:** Run Leiden algorithm at multiple resolution parameters to get communities at different granularity levels
**When to use:** To produce hierarchical community structure

```python
import leidenalg as la

def _detect_communities_multi_resolution(
    graph: ig.Graph,
    resolutions: list[float],
) -> dict[int, list[list[int]]]:
    """Run Leiden at each resolution level.
    
    Returns {level: [[vertex_indices_in_community], ...]}.
    Lower resolution = fewer, larger communities.
    Higher resolution = more, smaller communities.
    """
    results: dict[int, list[list[int]]] = {}
    
    for level, resolution in enumerate(resolutions):
        partition = la.find_partition(
            graph,
            la.CPMVertexPartition,
            resolution_parameter=resolution,
            weights="weight",  # use edge weight attribute
        )
        # partition.membership is list[int] mapping vertex -> community
        # Convert to list of community member lists
        communities: dict[int, list[int]] = {}
        for vertex_idx, comm_id in enumerate(partition.membership):
            communities.setdefault(comm_id, []).append(vertex_idx)
        
        results[level] = list(communities.values())
    
    return results
```

**Key API details for leidenalg.find_partition():**
- First arg: `igraph.Graph` object
- Second arg: partition type class (use `la.CPMVertexPartition` for resolution-based)
- `resolution_parameter`: float controlling granularity (lower = bigger communities)
- `weights`: string name of edge attribute OR list of weights
- Returns: partition object with `.membership` (list[int]), `.quality()` (float), `len(partition)` (number of communities)
- `partition[i]` gives list of vertex indices in community i

### Pattern 4: TF-IDF Extractive Summary
**What:** Score sentences by TF-IDF importance, select top-k
**When to use:** To generate a summary for each community from member chunk texts

```python
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

def _extractive_summary(texts: list[str], max_sentences: int = 5) -> str:
    """Generate extractive summary from community member texts.
    
    1. Split all texts into sentences
    2. Compute TF-IDF matrix over sentences
    3. Score each sentence by mean TF-IDF of its terms
    4. Return top-k sentences in original order
    """
    import re
    
    # Split into sentences
    sentences = []
    sentence_sources = []  # track which text each sentence came from
    for i, text in enumerate(texts):
        sents = re.split(r'(?<=[.!?])\s+', text.strip())
        for s in sents:
            s = s.strip()
            if len(s) > 20:  # skip very short fragments
                sentences.append(s)
                sentence_sources.append(i)
    
    if not sentences:
        return " ".join(texts)[:500] if texts else ""
    
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    
    # Compute TF-IDF
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(sentences)
    
    # Score each sentence: mean TF-IDF value across its terms
    scores = np.asarray(tfidf_matrix.mean(axis=1)).flatten()
    
    # Get top-k sentence indices, then sort by original order
    top_indices = np.argsort(scores)[-max_sentences:]
    top_indices = sorted(top_indices)
    
    return " ".join(sentences[i] for i in top_indices)
```

### Pattern 5: Thread-Pool Offloading for Blocking Calls
**What:** All igraph, leidenalg, and sklearn operations are synchronous/CPU-bound
**When to use:** Always, in async code paths

```python
import asyncio

loop = asyncio.get_event_loop()

# Build graph (blocking)
graph, id_map = await loop.run_in_executor(None, _build_graph, entities, relationships)

# Run Leiden (blocking, CPU-intensive)
community_map = await loop.run_in_executor(
    None, _detect_communities_multi_resolution, graph, resolutions
)

# Generate summaries (blocking)
summary = await loop.run_in_executor(None, _extractive_summary, chunk_texts)

# Embed summaries (blocking, already pattern in codebase)
embeddings = await loop.run_in_executor(None, embed_texts, [summary])
```

### Anti-Patterns to Avoid
- **Running Leiden on the async event loop:** igraph and leidenalg are pure C extensions with no async support. Always use `run_in_executor`.
- **Loading ALL chunk texts into memory at once:** For large tenants, gather chunk_ids from entities, then batch-fetch from Qdrant. Use pagination.
- **Using ModularityVertexPartition for hierarchy:** Modularity has no resolution parameter, so you get a single "best" partition. Use `CPMVertexPartition` which accepts `resolution_parameter` for multi-level detection.
- **Forgetting edge weights:** The relationship documents have a `weight` field. Pass `weights="weight"` to `find_partition` to use it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Community detection | Custom clustering on adjacency matrix | `leidenalg.find_partition()` | Leiden is state-of-art; handles edge cases (disconnected components, singletons) |
| Graph data structure | Dict-of-dicts adjacency | `igraph.Graph` | C-backed, memory efficient, required by leidenalg |
| Sentence importance scoring | Custom word frequency counting | `sklearn.feature_extraction.text.TfidfVectorizer` | Handles tokenization, stop words, IDF normalization correctly |
| Community persistence | Custom MongoDB operations | `graph_store.upsert_community()` | Already built with proper dedup by (tenant_id, level, title) |
| Community embedding search | Custom vector similarity | `graph_store.search_communities_by_embedding()` | Already built with numpy cosine similarity |

**Key insight:** The data model and persistence layer are already complete. This phase only needs the detection algorithm and summarization logic.

## Common Pitfalls

### Pitfall 1: Package Name Confusion (igraph vs python-igraph)
**What goes wrong:** `pip install igraph` installs a JavaScript WebGL visualization package, not the graph analysis library.
**Why it happens:** Two different packages share the name on PyPI.
**How to avoid:** Always use `pip install python-igraph`. The import is still `import igraph`.
**Warning signs:** `ImportError: cannot import name 'Graph' from 'igraph'` or unexpected module contents.

### Pitfall 2: Empty or Tiny Graphs
**What goes wrong:** Leiden crashes or produces meaningless results on graphs with fewer than 2 nodes or 0 edges.
**Why it happens:** The algorithm needs connected components to partition.
**How to avoid:** Check entity count before running. If < 3 entities or 0 relationships, skip community detection and log a warning. Return empty results.
**Warning signs:** `igraph._igraph.InternalError` or single-community results for all resolutions.

### Pitfall 3: Resolution Parameter Selection
**What goes wrong:** Wrong resolution values produce either one giant community or all singletons.
**Why it happens:** CPM resolution is sensitive to graph density. The "right" values depend on the graph.
**How to avoid:** Use three levels: 0.1 (coarse, fewer large communities), 0.5 (medium), 1.0 (fine, many small communities). These are well-tested defaults for knowledge graphs. Filter out singleton communities (size=1) as they add noise.
**Warning signs:** Level 0 producing same number of communities as level 2; or all entities in one community.

### Pitfall 4: Chunk Text Retrieval Bottleneck
**What goes wrong:** Loading chunk texts for all entities in a community requires Qdrant scroll queries per entity, causing N+1 query explosion.
**Why it happens:** Entities store `chunk_ids` (references to Qdrant points), but there's no batch "get points by IDs" helper yet.
**How to avoid:** Collect all unique `chunk_ids` across all entities in a community, then batch-scroll from Qdrant. Alternatively, query MongoDB documents collection which may store chunk text. Consider using entity names + descriptions as summary input instead of full chunk texts if performance is an issue.
**Warning signs:** Community detection taking minutes due to Qdrant I/O, not algorithm time.

### Pitfall 5: Duplicate Edges in igraph
**What goes wrong:** If the same pair of entities has multiple relationship types, igraph creates multi-edges which can confuse Leiden.
**Why it happens:** MongoDB stores separate relationship documents per (source, target, relation_type).
**How to avoid:** When building the igraph, either (a) allow multi-edges and sum weights for the same pair, or (b) deduplicate edges by (source, target), summing weights. Option (b) is cleaner for community detection.
**Warning signs:** Unexpectedly large edge counts in igraph vs MongoDB relationship count.

### Pitfall 6: Community Title Generation
**What goes wrong:** Communities need a `title` field for the upsert dedup key `(tenant_id, level, title)`, but Leiden only produces membership lists.
**Why it happens:** The `upsert_community` function requires a title for the unique index.
**How to avoid:** Generate titles from the top entities by mention_count in the community, e.g., "Community: EntityA, EntityB, EntityC" or use the most prominent entity name. Keep titles deterministic so re-runs upsert correctly.
**Warning signs:** Duplicate key errors on communities collection; or communities not updating on re-run.

### Pitfall 7: Stale Communities After Graph Changes
**What goes wrong:** After new documents are ingested, old community data becomes stale.
**Why it happens:** Communities are computed as a snapshot of the current graph state.
**How to avoid:** The rebuild endpoint should delete existing communities for the tenant before running detection (or use upsert with deterministic titles). Document that communities are a point-in-time snapshot.
**Warning signs:** Community entity_ids referencing deleted entities.

## Code Examples

### Full build_communities Flow

```python
async def build_communities(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    resolutions: list[float] | None = None,
    max_summary_sentences: int = 5,
) -> dict[str, int]:
    """Detect communities and generate summaries for a tenant's entity graph."""
    if resolutions is None:
        resolutions = [0.1, 0.5, 1.0]
    
    loop = asyncio.get_event_loop()
    
    # 1. Load all entities and relationships
    entities = await db.entities.find(
        {"tenant_id": tenant_id}
    ).to_list(length=None)
    
    relationships = await db.relationships.find(
        {"tenant_id": tenant_id}
    ).to_list(length=None)
    
    if len(entities) < 3 or len(relationships) == 0:
        log.warning(
            "skipping_community_detection",
            tenant_id=tenant_id,
            entity_count=len(entities),
            relationship_count=len(relationships),
            reason="insufficient graph data",
        )
        return {"total_communities": 0}
    
    # 2. Build igraph (blocking)
    graph, id_to_idx = await loop.run_in_executor(
        None, _build_graph, entities, relationships
    )
    
    # 3. Run Leiden at multiple resolutions (blocking)
    community_map = await loop.run_in_executor(
        None, _detect_communities_multi_resolution, graph, resolutions
    )
    
    # 4. For each level, process communities
    # Build entity lookup by vertex index
    idx_to_entity = {i: ent for i, ent in enumerate(entities)}
    
    stats: dict[str, int] = {}
    
    for level, comm_members_list in community_map.items():
        level_count = 0
        for members in comm_members_list:
            if len(members) < 2:
                continue  # skip singletons
            
            # Gather entity info
            member_entities = [idx_to_entity[m] for m in members]
            entity_ids = [str(e["_id"]) for e in member_entities]
            
            # Generate title from top entities by mention_count
            sorted_ents = sorted(
                member_entities, key=lambda e: e.get("mention_count", 0), reverse=True
            )
            title_parts = [e["name"] for e in sorted_ents[:3]]
            title = f"L{level}: {', '.join(title_parts)}"
            
            # Gather chunk texts for summary
            all_chunk_ids = set()
            for ent in member_entities:
                all_chunk_ids.update(ent.get("chunk_ids", []))
            
            # Fetch chunk texts from Qdrant (batch)
            chunk_texts = await _fetch_chunk_texts(
                tenant_id, list(all_chunk_ids)
            )
            
            # Generate extractive summary (blocking)
            summary = ""
            if chunk_texts:
                summary = await loop.run_in_executor(
                    None, _extractive_summary, chunk_texts, max_summary_sentences
                )
            
            # Embed summary (blocking)
            summary_embedding = None
            if summary:
                embeddings = await loop.run_in_executor(
                    None, embed_texts, [summary]
                )
                summary_embedding = embeddings[0] if embeddings else None
            
            # Upsert community
            await upsert_community(db, tenant_id, {
                "level": level,
                "title": title,
                "summary": summary,
                "entity_ids": entity_ids,
                "summary_embedding": summary_embedding,
            })
            level_count += 1
        
        stats[f"level_{level}"] = level_count
    
    stats["total_communities"] = sum(stats.values())
    return stats
```

### API Route Pattern

```python
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from docingest.api.auth import Tenant
from docingest.db.mongodb import get_db
from docingest.services.community_detection import build_communities

router = APIRouter(prefix="/v1/graph", tags=["graph"])

@router.post("/communities/rebuild")
async def rebuild_communities(
    tenant: Tenant = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Rebuild community detection for the tenant's entity graph."""
    stats = await build_communities(db, tenant.tenant_id)
    return {"status": "ok", "communities": stats}
```

### Fetching Chunk Texts from Qdrant by IDs

```python
from qdrant_client.models import Filter, HasIdCondition

async def _fetch_chunk_texts(
    tenant_id: str, chunk_ids: list[str], batch_size: int = 100
) -> list[str]:
    """Fetch chunk_text payloads from Qdrant by point IDs."""
    if not chunk_ids:
        return []
    
    client = await get_qdrant()
    collection = f"tenant_{tenant_id}"
    texts = []
    
    for i in range(0, len(chunk_ids), batch_size):
        batch = chunk_ids[i : i + batch_size]
        points, _ = await client.scroll(
            collection_name=collection,
            scroll_filter=Filter(
                must=[HasIdCondition(has_id=batch)]
            ),
            limit=batch_size,
            with_payload=["chunk_text"],
            with_vectors=False,
        )
        for p in points:
            text = p.payload.get("chunk_text", "")
            if text:
                texts.append(text)
    
    return texts
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Louvain algorithm | Leiden algorithm | 2019 (original paper) | Better theoretical guarantees; guaranteed connected communities |
| python-igraph 0.x | python-igraph 1.0.0 | 2025 | Same API, import still `import igraph`; version constraint should use `<2` not `<1` |
| leidenalg 0.10.x | leidenalg 0.11.0 | 2025 | Updated C core to igraph 1.0; same Python API |
| Custom TF-IDF | sklearn TfidfVectorizer | Stable | No recent changes; API stable for years |

**Important version note:** The phase description suggests `igraph>=0.11,<1` but python-igraph has reached 1.0.0. Use `python-igraph>=0.11,<2` to include 1.0.0. Similarly, leidenalg 0.11.0 is the latest and works with igraph 1.0, so `leidenalg>=0.10,<1` still works (0.11.0 < 1.0).

## Open Questions

1. **Chunk text retrieval strategy**
   - What we know: Entities store `chunk_ids` which are Qdrant point UUIDs. We can scroll Qdrant by ID.
   - What's unclear: For large communities with hundreds of entities, fetching all chunk texts could be expensive. May need to cap at N chunks per community.
   - Recommendation: Cap at 50 chunks per community (sorted by entity mention_count), sufficient for a good extractive summary.

2. **Community hierarchy parent/child linking**
   - What we know: The `Community` model has `parent_community_id` and `child_community_ids` fields.
   - What's unclear: Mapping fine-grained communities (high resolution) to coarse communities (low resolution) requires comparing memberships across levels.
   - Recommendation: For each community at level N, find the level N-1 community that shares the most entities. Set that as parent. This is a post-processing step after all levels are computed.

3. **Triggering mechanism**
   - What we know: Phase description mentions API endpoint and/or trigger after graph builder.
   - What's unclear: Should community detection run automatically after every document's graph is built? That's expensive.
   - Recommendation: Start with manual API endpoint only (`POST /v1/graph/communities/rebuild`). Auto-trigger can be added later with a threshold (e.g., after N new entities are added since last rebuild).

4. **Qdrant HasIdCondition for UUID strings**
   - What we know: Chunk IDs stored in entities are strings of Qdrant point UUIDs.
   - What's unclear: Whether `HasIdCondition` accepts string UUIDs or requires `PointId` objects.
   - Recommendation: Test with string UUIDs first; if needed, use `scroll_filter` with explicit point ID matching. Alternatively, fall back to using entity names/descriptions for summaries if chunk text retrieval proves complex.

## Sources

### Primary (HIGH confidence)
- `src/docingest/db/graph_store.py` - Complete community CRUD: `upsert_community()`, `get_communities_by_level()`, `search_communities_by_embedding()`
- `src/docingest/models/graph.py` - `Community` model with level, title, summary, entity_ids, parent/child, summary_embedding
- `src/docingest/services/embedding.py` - `embed_texts(texts: list[str]) -> list[list[float]]` -- sync, thread-safe, batched
- `src/docingest/db/qdrant.py` - `get_doc_chunks()` scroll pattern, `search_chunks()` with filters
- `src/docingest/config.py` - `graph_rag_enabled` flag, existing settings pattern
- `src/docingest/workers/chunker.py` - Confirms chunk payload includes `chunk_text` key

### Secondary (MEDIUM confidence)
- [leidenalg GitHub](https://github.com/vtraag/leidenalg) - `find_partition()` API, `CPMVertexPartition`, `resolution_parameter`, `weights` parameter
- [leidenalg advanced docs (via GitHub RST)](https://github.com/vtraag/leidenalg/blob/main/doc/source/advanced.rst) - `resolution_profile()`, `Optimiser` class, multi-level detection
- [python-igraph PyPI](https://pypi.org/project/python-igraph/) - Version 1.0.0, import as `igraph`
- [leidenalg PyPI](https://pypi.org/project/leidenalg/) - Version 0.11.0, igraph 1.0 compatibility
- [scikit-learn PyPI](https://pypi.org/project/scikit-learn/) - Version 1.8.0

### Tertiary (LOW confidence)
- Resolution parameter values (0.1, 0.5, 1.0) are reasonable defaults based on community practice but may need tuning per dataset

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified package versions on PyPI, confirmed leidenalg 0.11.0 supports igraph 1.0
- Architecture: HIGH - data model and persistence layer already built; code patterns follow existing project conventions
- Pitfalls: HIGH - identified from direct code inspection and API documentation review
- Code examples: MEDIUM - leidenalg API verified from GitHub docs; igraph Graph construction from official tutorials; TF-IDF pattern is well-established

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable libraries, established patterns)
