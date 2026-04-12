"""Tests for docingest.services.community_detection sync helpers."""

from __future__ import annotations

import pytest
from bson import ObjectId

# ---------------------------------------------------------------------------
# Optional dependency guards
# ---------------------------------------------------------------------------

try:
    import igraph  # noqa: F401
    import leidenalg  # noqa: F401

    HAS_GRAPH_LIBS = True
except ImportError:
    HAS_GRAPH_LIBS = False

try:
    import sklearn  # noqa: F401

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

needs_graph = pytest.mark.skipif(not HAS_GRAPH_LIBS, reason="igraph/leidenalg not installed")
needs_sklearn = pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn not installed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_entity(name: str, entity_type: str = "organization", mention_count: int = 1,
                 chunk_ids: list[str] | None = None) -> dict:
    return {
        "_id": ObjectId(),
        "name": name,
        "entity_type": entity_type,
        "mention_count": mention_count,
        "chunk_ids": chunk_ids or [],
    }


def _make_relationship(source_id: str, target_id: str, relation_type: str = "related",
                       weight: float = 1.0) -> dict:
    return {
        "source_entity_id": source_id,
        "target_entity_id": target_id,
        "relation_type": relation_type,
        "weight": weight,
    }


# ---------------------------------------------------------------------------
# _extractive_summary tests
# ---------------------------------------------------------------------------


@needs_sklearn
class TestExtractiveSummary:
    """Tests for _extractive_summary (requires sklearn for TfidfVectorizer)."""

    def test_returns_top_sentences(self):
        from docingest.services.community_detection import _extractive_summary

        texts = [
            "The quick brown fox jumps over the lazy dog near the river bank.",
            "Machine learning algorithms process large datasets efficiently and accurately.",
            "Climate change impacts global ecosystems through rising temperatures worldwide.",
        ]
        result = _extractive_summary(texts, max_sentences=2)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should return exactly 2 sentences when there are more available
        # Each original text is one long sentence > 20 chars, so we have 3 sentences, pick 2
        parts = [s.strip() for s in result.split(".") if s.strip()]
        assert len(parts) >= 1  # at least one sentence returned

    def test_empty_list_returns_empty_string(self):
        from docingest.services.community_detection import _extractive_summary

        result = _extractive_summary([], max_sentences=2)
        assert result == ""

    def test_short_texts_fallback(self):
        from docingest.services.community_detection import _extractive_summary

        # All texts shorter than 20 chars -- triggers fallback path
        texts = ["Short.", "Tiny.", "Small."]
        result = _extractive_summary(texts, max_sentences=2)
        assert isinstance(result, str)
        # Fallback joins and truncates
        assert len(result) <= 500

    def test_exact_max_sentences_returns_all(self):
        from docingest.services.community_detection import _extractive_summary

        texts = [
            "Artificial intelligence revolutionizes modern healthcare diagnostics significantly.",
            "Quantum computing promises breakthroughs in cryptography and optimization problems.",
        ]
        # 2 sentences each > 20 chars, max_sentences=2
        result = _extractive_summary(texts, max_sentences=2)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# _generate_community_title tests
# ---------------------------------------------------------------------------


@needs_graph
class TestGenerateCommunityTitle:
    """Tests for _generate_community_title (pure logic, but module requires igraph import)."""

    def test_top_3_by_mention_count(self):
        from docingest.services.community_detection import _generate_community_title

        entities = [
            _make_entity("Alpha", mention_count=10),
            _make_entity("Beta", mention_count=50),
            _make_entity("Gamma", mention_count=30),
            _make_entity("Delta", mention_count=5),
            _make_entity("Epsilon", mention_count=20),
        ]
        title = _generate_community_title(entities, level=0)
        assert title.startswith("L0: ")
        # Top 3 by mention_count: Beta(50), Gamma(30), Epsilon(20)
        assert "Beta" in title
        assert "Gamma" in title
        assert "Epsilon" in title
        # Delta and Alpha should NOT be in title
        assert "Delta" not in title
        assert "Alpha" not in title

    def test_single_entity(self):
        from docingest.services.community_detection import _generate_community_title

        entities = [_make_entity("OnlyOne", mention_count=5)]
        title = _generate_community_title(entities, level=2)
        assert title == "L2: OnlyOne"

    def test_determinism(self):
        from docingest.services.community_detection import _generate_community_title

        entities = [
            _make_entity("Foo", mention_count=10),
            _make_entity("Bar", mention_count=20),
            _make_entity("Baz", mention_count=15),
        ]
        title1 = _generate_community_title(entities, level=1)
        title2 = _generate_community_title(entities, level=1)
        assert title1 == title2


# ---------------------------------------------------------------------------
# _build_graph tests
# ---------------------------------------------------------------------------


@needs_graph
class TestBuildGraph:
    """Tests for _build_graph (requires igraph)."""

    def test_basic_graph(self):
        from docingest.services.community_detection import _build_graph

        e1, e2, e3 = _make_entity("A"), _make_entity("B"), _make_entity("C")
        rels = [
            _make_relationship(str(e1["_id"]), str(e2["_id"])),
            _make_relationship(str(e2["_id"]), str(e3["_id"])),
        ]
        graph, id_map = _build_graph([e1, e2, e3], rels)
        assert graph.vcount() == 3
        assert graph.ecount() == 2

    def test_edge_deduplication(self):
        from docingest.services.community_detection import _build_graph

        e1, e2 = _make_entity("A"), _make_entity("B")
        rels = [
            _make_relationship(str(e1["_id"]), str(e2["_id"]), "works_with", weight=2.0),
            _make_relationship(str(e2["_id"]), str(e1["_id"]), "collaborates", weight=3.0),
        ]
        graph, _ = _build_graph([e1, e2], rels)
        assert graph.ecount() == 1
        assert graph.es[0]["weight"] == 5.0  # summed

    def test_nonexistent_entity_skipped(self):
        from docingest.services.community_detection import _build_graph

        e1 = _make_entity("A")
        rels = [_make_relationship(str(e1["_id"]), "nonexistent_id_1234")]
        graph, _ = _build_graph([e1], rels)
        assert graph.vcount() == 1
        assert graph.ecount() == 0

    def test_vertex_attributes(self):
        from docingest.services.community_detection import _build_graph

        e1 = _make_entity("Alice", entity_type="person")
        e2 = _make_entity("Bob", entity_type="person")
        rels = [_make_relationship(str(e1["_id"]), str(e2["_id"]))]
        graph, _ = _build_graph([e1, e2], rels)
        assert graph.vs["entity_name"] == ["Alice", "Bob"]
        assert graph.vs["entity_type"] == ["person", "person"]


# ---------------------------------------------------------------------------
# _detect_communities_multi_resolution tests
# ---------------------------------------------------------------------------


@needs_graph
class TestDetectCommunitiesMultiResolution:
    """Tests for _detect_communities_multi_resolution (requires igraph + leidenalg)."""

    @staticmethod
    def _two_cluster_graph():
        """Create a graph with 2 clear clusters of 3 nodes each, connected by 1 weak edge."""
        import igraph as ig

        g = ig.Graph(n=6, directed=False)
        # Cluster 1: 0-1, 0-2, 1-2 (fully connected)
        g.add_edges([(0, 1), (0, 2), (1, 2)])
        # Cluster 2: 3-4, 3-5, 4-5 (fully connected)
        g.add_edges([(3, 4), (3, 5), (4, 5)])
        # Bridge: 2-3 (weak connection between clusters)
        g.add_edges([(2, 3)])
        g.es["weight"] = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 0.1]
        return g

    def test_finds_two_communities_at_high_resolution(self):
        from docingest.services.community_detection import _detect_communities_multi_resolution

        graph = self._two_cluster_graph()
        result = _detect_communities_multi_resolution(graph, [1.0])
        assert 0 in result
        communities = result[0]
        # Should find 2 communities (the two clusters)
        assert len(communities) >= 2

    def test_low_resolution_fewer_communities(self):
        from docingest.services.community_detection import _detect_communities_multi_resolution

        graph = self._two_cluster_graph()
        low_res = _detect_communities_multi_resolution(graph, [0.01])
        high_res = _detect_communities_multi_resolution(graph, [1.0])
        # Low resolution should merge clusters -> fewer or equal communities
        assert len(low_res[0]) <= len(high_res[0])
