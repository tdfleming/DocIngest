"""Community detection service using Leiden algorithm over tenant entity graphs.

Builds hierarchical communities at multiple resolution levels, generates
extractive TF-IDF summaries, embeds them via FastEmbed, and persists to MongoDB.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from typing import Any

import igraph as ig
import leidenalg as la
import numpy as np
import structlog
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client.models import Filter, HasIdCondition
from sklearn.feature_extraction.text import TfidfVectorizer

from docingest.config import settings
from docingest.db.graph_store import upsert_community
from docingest.db.qdrant import get_qdrant
from docingest.services.embedding import embed_texts

log = structlog.get_logger()


async def build_communities(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    resolutions: list[float] | None = None,
) -> dict[str, int]:
    """Detect communities and generate summaries for a tenant's entity graph.

    Orchestrates the full pipeline: load graph data, run Leiden at multiple
    resolutions, generate extractive summaries, embed them, and persist.

    Returns stats dict with community counts per level and total.
    """
    if resolutions is None:
        resolutions = settings.community_resolutions

    log.info(
        "community_detection_start",
        tenant_id=tenant_id,
        resolutions=resolutions,
    )

    loop = asyncio.get_event_loop()

    # 1. Load all entities and relationships for tenant
    entities: list[dict[str, Any]] = await db.entities.find(
        {"tenant_id": tenant_id}
    ).to_list(length=None)

    relationships: list[dict[str, Any]] = await db.relationships.find(
        {"tenant_id": tenant_id}
    ).to_list(length=None)

    # 2. Guard: insufficient graph data
    if len(entities) < 3 or len(relationships) == 0:
        log.warning(
            "skipping_community_detection",
            tenant_id=tenant_id,
            entity_count=len(entities),
            relationship_count=len(relationships),
            reason="insufficient graph data",
        )
        return {"total_communities": 0}

    # 3. Build igraph (blocking, offloaded to thread pool)
    graph, id_to_idx = await loop.run_in_executor(
        None, _build_graph, entities, relationships
    )

    log.info(
        "graph_built",
        tenant_id=tenant_id,
        vertices=graph.vcount(),
        edges=graph.ecount(),
    )

    # 4. Run Leiden at multiple resolutions (blocking)
    community_map = await loop.run_in_executor(
        None, _detect_communities_multi_resolution, graph, resolutions
    )

    # 5. Build vertex-index to entity lookup
    idx_to_entity: dict[int, dict[str, Any]] = {
        i: ent for i, ent in enumerate(entities)
    }

    # 6. Process each community: title, summary, embedding, upsert
    stats: dict[str, int] = {}
    # Track upserted community IDs per level for parent/child linking
    level_communities: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for level, comm_members_list in community_map.items():
        level_count = 0
        for members in comm_members_list:
            if len(members) < 2:
                continue  # filter singletons

            member_entities = [idx_to_entity[m] for m in members]
            entity_ids = [str(e["_id"]) for e in member_entities]

            # Deterministic title from top entities
            title = _generate_community_title(member_entities, level)

            # Collect unique chunk_ids, capped
            all_chunk_ids: set[str] = set()
            for ent in member_entities:
                all_chunk_ids.update(ent.get("chunk_ids", []))
            chunk_ids_list = list(all_chunk_ids)[: settings.community_max_chunks]

            # Fetch chunk texts from Qdrant
            chunk_texts = await _fetch_chunk_texts(tenant_id, chunk_ids_list)

            # Generate extractive summary (blocking)
            summary = ""
            if chunk_texts:
                summary = await loop.run_in_executor(
                    None,
                    _extractive_summary,
                    chunk_texts,
                    settings.community_max_summary_sentences,
                )

            # Embed summary (blocking)
            summary_embedding: list[float] | None = None
            if summary:
                embeddings = await loop.run_in_executor(
                    None, embed_texts, [summary]
                )
                summary_embedding = embeddings[0] if embeddings else None

            # Upsert community to MongoDB
            comm_id = await upsert_community(db, tenant_id, {
                "level": level,
                "title": title,
                "summary": summary,
                "entity_ids": entity_ids,
                "summary_embedding": summary_embedding,
            })

            level_communities[level].append({
                "id": comm_id,
                "entity_ids_set": set(entity_ids),
                "title": title,
                "level": level,
            })
            level_count += 1

        stats[f"level_{level}"] = level_count

    log.info(
        "communities_detected",
        tenant_id=tenant_id,
        stats=stats,
    )

    # 7. Post-process: link parent/child hierarchy across resolution levels
    sorted_levels = sorted(level_communities.keys())
    for i in range(1, len(sorted_levels)):
        child_level = sorted_levels[i]
        parent_level = sorted_levels[i - 1]

        for child_comm in level_communities[child_level]:
            best_overlap = 0
            best_parent_id: str | None = None

            for parent_comm in level_communities[parent_level]:
                overlap = len(
                    child_comm["entity_ids_set"] & parent_comm["entity_ids_set"]
                )
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_parent_id = parent_comm["id"]

            if best_parent_id:
                # Set parent on child
                await db.communities.update_one(
                    {"_id": ObjectId(child_comm["id"])},
                    {"$set": {"parent_community_id": best_parent_id}},
                )
                # Add child to parent's child list
                await db.communities.update_one(
                    {"_id": ObjectId(best_parent_id)},
                    {"$addToSet": {"child_community_ids": child_comm["id"]}},
                )

    stats["total_communities"] = sum(
        v for k, v in stats.items() if k.startswith("level_")
    )

    log.info(
        "community_detection_complete",
        tenant_id=tenant_id,
        total_communities=stats["total_communities"],
    )

    return stats


def _build_graph(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> tuple[ig.Graph, dict[str, int]]:
    """Build an undirected igraph.Graph from entity and relationship dicts.

    Deduplicates edges by summing weights for the same (source, target) pair.
    Returns (graph, entity_id_to_vertex_index_map).
    """
    id_to_idx: dict[str, int] = {}
    for i, ent in enumerate(entities):
        id_to_idx[str(ent["_id"])] = i

    g = ig.Graph(n=len(entities), directed=False)

    # Set vertex attributes
    g.vs["name"] = [str(e["_id"]) for e in entities]
    g.vs["entity_name"] = [e.get("name", "") for e in entities]
    g.vs["entity_type"] = [e.get("entity_type", "") for e in entities]

    # Deduplicate edges: sum weights for same (min, max) pair
    edge_weights: dict[tuple[int, int], float] = {}
    for rel in relationships:
        src_idx = id_to_idx.get(rel.get("source_entity_id", ""))
        tgt_idx = id_to_idx.get(rel.get("target_entity_id", ""))
        if src_idx is not None and tgt_idx is not None and src_idx != tgt_idx:
            key = (min(src_idx, tgt_idx), max(src_idx, tgt_idx))
            edge_weights[key] = edge_weights.get(key, 0.0) + rel.get("weight", 1.0)

    if edge_weights:
        edges, weights = zip(*[(k, v) for k, v in edge_weights.items()], strict=True)
        g.add_edges(list(edges))
        g.es["weight"] = list(weights)

    return g, id_to_idx


def _detect_communities_multi_resolution(
    graph: ig.Graph,
    resolutions: list[float],
) -> dict[int, list[list[int]]]:
    """Run Leiden algorithm at each resolution level using CPMVertexPartition.

    Lower resolution = fewer, larger communities.
    Higher resolution = more, smaller communities.

    Returns {level: [[vertex_indices_in_community], ...]}.
    """
    results: dict[int, list[list[int]]] = {}

    for level, resolution in enumerate(resolutions):
        partition = la.find_partition(
            graph,
            la.CPMVertexPartition,
            resolution_parameter=resolution,
            weights="weight",
        )

        # Convert membership list to community member lists
        communities: dict[int, list[int]] = {}
        for vertex_idx, comm_id in enumerate(partition.membership):
            communities.setdefault(comm_id, []).append(vertex_idx)

        results[level] = list(communities.values())

    return results


def _extractive_summary(texts: list[str], max_sentences: int = 5) -> str:
    """Generate an extractive summary from texts using TF-IDF sentence scoring.

    Splits all texts into sentences, scores by mean TF-IDF value,
    and returns the top-k sentences in their original order.
    """
    # Split into sentences
    sentences: list[str] = []
    for text in texts:
        sents = re.split(r"(?<=[.!?])\s+", text.strip())
        for s in sents:
            s = s.strip()
            if len(s) > 20:  # skip very short fragments
                sentences.append(s)

    if not sentences:
        return " ".join(texts)[:500] if texts else ""

    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    # Compute TF-IDF scores
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(sentences)

    # Score each sentence by mean TF-IDF value across its terms
    scores = np.asarray(tfidf_matrix.mean(axis=1)).flatten()

    # Select top-k indices, then sort by original order for coherence
    top_indices = np.argsort(scores)[-max_sentences:]
    top_indices = sorted(top_indices)

    return " ".join(sentences[i] for i in top_indices)


def _generate_community_title(member_entities: list[dict[str, Any]], level: int) -> str:
    """Generate a deterministic title from top entities by mention_count.

    Format: 'L{level}: Entity1, Entity2, Entity3'
    Deterministic for upsert deduplication.
    """
    sorted_ents = sorted(
        member_entities,
        key=lambda e: e.get("mention_count", 0),
        reverse=True,
    )
    top_names = [e.get("name", "unknown") for e in sorted_ents[:3]]
    return f"L{level}: {', '.join(top_names)}"


async def _fetch_chunk_texts(
    tenant_id: str,
    chunk_ids: list[str],
    batch_size: int = 100,
) -> list[str]:
    """Fetch chunk_text payloads from Qdrant by point IDs in batches.

    Returns list of non-empty chunk text strings.
    """
    if not chunk_ids:
        return []

    client = await get_qdrant()
    collection = f"tenant_{tenant_id}"
    texts: list[str] = []

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
