"""Tests for docingest.services.entity_extraction."""

from __future__ import annotations

import pytest

spacy = pytest.importorskip("spacy")

from docingest.models.graph import EntityType  # noqa: E402
from docingest.services import entity_extraction  # noqa: E402
from docingest.services.entity_extraction import (  # noqa: E402
    _SPACY_LABEL_MAP,
    _map_spacy_label,
    extract_entities,
    extract_entities_async,
    extract_relationships,
    extract_relationships_async,
    resolve_entity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_small_model(monkeypatch):
    """Override spacy_model to en_core_web_sm and reset singleton between tests."""
    from docingest.config import settings

    monkeypatch.setattr(settings, "spacy_model", "en_core_web_sm")
    # Reset the lazy-loaded model so each test gets a clean state
    entity_extraction._nlp = None
    yield
    entity_extraction._nlp = None


# ---------------------------------------------------------------------------
# Pure logic tests (no spaCy model needed)
# ---------------------------------------------------------------------------


class TestMapSpacyLabel:
    """Test _map_spacy_label and _SPACY_LABEL_MAP coverage."""

    def test_person(self):
        assert _map_spacy_label("PERSON") == EntityType.PERSON

    def test_org(self):
        assert _map_spacy_label("ORG") == EntityType.ORGANIZATION

    def test_gpe(self):
        assert _map_spacy_label("GPE") == EntityType.LOCATION

    def test_loc(self):
        assert _map_spacy_label("LOC") == EntityType.LOCATION

    def test_fac(self):
        assert _map_spacy_label("FAC") == EntityType.LOCATION

    def test_date(self):
        assert _map_spacy_label("DATE") == EntityType.DATE

    def test_time(self):
        assert _map_spacy_label("TIME") == EntityType.DATE

    def test_event(self):
        assert _map_spacy_label("EVENT") == EntityType.EVENT

    def test_product(self):
        assert _map_spacy_label("PRODUCT") == EntityType.PRODUCT

    def test_norp(self):
        assert _map_spacy_label("NORP") == EntityType.CONCEPT

    def test_law(self):
        assert _map_spacy_label("LAW") == EntityType.CONCEPT

    def test_language(self):
        assert _map_spacy_label("LANGUAGE") == EntityType.CONCEPT

    def test_work_of_art(self):
        assert _map_spacy_label("WORK_OF_ART") == EntityType.CONCEPT

    def test_cardinal(self):
        assert _map_spacy_label("CARDINAL") == EntityType.OTHER

    def test_ordinal(self):
        assert _map_spacy_label("ORDINAL") == EntityType.OTHER

    def test_money(self):
        assert _map_spacy_label("MONEY") == EntityType.OTHER

    def test_percent(self):
        assert _map_spacy_label("PERCENT") == EntityType.OTHER

    def test_quantity(self):
        assert _map_spacy_label("QUANTITY") == EntityType.OTHER

    def test_unknown_label_returns_other(self):
        assert _map_spacy_label("UNKNOWN_LABEL") == EntityType.OTHER

    def test_all_18_labels_covered(self):
        assert len(_SPACY_LABEL_MAP) == 18


class TestResolveEntity:
    """Test fuzzy entity matching (pure logic, no model)."""

    def test_resolve_entity_match(self):
        existing = [{"name": "Microsoft Corporation", "entity_type": "organization"}]
        result = resolve_entity("Microsoft Corp", "organization", existing, threshold=0.7)
        assert result == "Microsoft Corporation"

    def test_resolve_entity_no_match(self):
        existing = [{"name": "Zebra Corp", "entity_type": "organization"}]
        result = resolve_entity("Apple", "organization", existing, threshold=0.7)
        assert result is None

    def test_resolve_entity_type_mismatch(self):
        existing = [{"name": "Apple", "entity_type": "person"}]
        result = resolve_entity("Apple", "organization", existing, threshold=0.7)
        assert result is None

    def test_resolve_entity_picks_best(self):
        existing = [
            {"name": "Microsoft Inc", "entity_type": "organization"},
            {"name": "Microsoft Corporation", "entity_type": "organization"},
        ]
        result = resolve_entity("Microsoft Corporation", "organization", existing, threshold=0.7)
        assert result == "Microsoft Corporation"

    def test_resolve_entity_uses_default_threshold(self, monkeypatch):
        from docingest.config import settings

        monkeypatch.setattr(settings, "entity_confidence_threshold", 0.99)
        existing = [{"name": "Microsoft Corporation", "entity_type": "organization"}]
        # "Microsoft Corp" vs "Microsoft Corporation" is ~0.86, below 0.99
        result = resolve_entity("Microsoft Corp", "organization", existing)
        assert result is None


# ---------------------------------------------------------------------------
# Model-dependent tests (need en_core_web_sm)
# ---------------------------------------------------------------------------


class TestExtractEntities:
    """Test NER extraction with en_core_web_sm."""

    def test_extract_entities_basic(self):
        text = "Tim Cook is the CEO of Apple Inc in Cupertino."
        entities = extract_entities(text)
        assert isinstance(entities, list)
        assert len(entities) > 0

        # Check structure
        for ent in entities:
            assert "name" in ent
            assert "entity_type" in ent
            assert "start_char" in ent
            assert "end_char" in ent

    def test_extract_entities_finds_known_types(self):
        text = "Tim Cook is the CEO of Apple Inc in Cupertino."
        entities = extract_entities(text)
        types_found = {e["entity_type"] for e in entities}
        # en_core_web_sm should find at least PERSON or ORG from this text
        assert types_found & {EntityType.PERSON, EntityType.ORGANIZATION, EntityType.LOCATION}

    def test_extract_entities_no_other_type(self):
        text = "In 2024, Tim Cook announced that Apple earned $100 billion in revenue."
        entities = extract_entities(text)
        for ent in entities:
            assert ent["entity_type"] != EntityType.OTHER

    def test_extract_entities_max_cap(self, monkeypatch):
        from docingest.config import settings

        monkeypatch.setattr(settings, "max_entities_per_chunk", 1)
        text = "Tim Cook is the CEO of Apple Inc in Cupertino, California."
        entities = extract_entities(text)
        assert len(entities) <= 1

    def test_extract_entities_empty_text(self):
        entities = extract_entities("")
        assert entities == []


class TestExtractRelationships:
    """Test SVO relationship extraction."""

    def test_extract_relationships_structure(self):
        text = "Microsoft acquired GitHub."
        entities = extract_entities(text)
        rels = extract_relationships(text, entities)
        assert isinstance(rels, list)
        for rel in rels:
            assert "source" in rel
            assert "target" in rel
            assert "relation_type" in rel
            assert "description" in rel

    def test_extract_relationships_filters_non_entities(self):
        text = "Microsoft acquired GitHub."
        # Pass empty entity list -- no relationships should be returned
        rels = extract_relationships(text, [])
        assert rels == []

    def test_extract_relationships_with_known_entities(self):
        text = "Microsoft acquired GitHub."
        entities = extract_entities(text)
        entity_names = {e["name"].lower() for e in entities}

        rels = extract_relationships(text, entities)
        # All returned rels must have both source and target in entity names
        for rel in rels:
            assert rel["source"].lower() in entity_names
            assert rel["target"].lower() in entity_names


class TestLazyLoad:
    """Test lazy model loading behaviour."""

    def test_lazy_load(self):
        assert entity_extraction._nlp is None
        extract_entities("test")
        assert entity_extraction._nlp is not None


class TestAsyncWrappers:
    """Test async wrappers return same structure as sync."""

    async def test_extract_entities_async(self):
        text = "Tim Cook is the CEO of Apple Inc."
        extract_entities(text)  # ensure model loaded for comparison
        async_result = await extract_entities_async(text)
        assert isinstance(async_result, list)
        # Same structure
        if async_result:
            assert "name" in async_result[0]
            assert "entity_type" in async_result[0]

    async def test_extract_relationships_async(self):
        text = "Microsoft acquired GitHub."
        entities = extract_entities(text)
        async_result = await extract_relationships_async(text, entities)
        assert isinstance(async_result, list)
