"""Tests for graph data models (Entity, Relationship, Community) and config fields."""

from datetime import UTC, datetime

from docingest.config import Settings
from docingest.models.graph import Community, Entity, EntityType, Relationship


class TestEntityType:
    def test_enum_has_eight_values(self):
        values = [e.value for e in EntityType]
        assert len(values) == 8
        assert set(values) == {
            "person",
            "organization",
            "location",
            "date",
            "event",
            "product",
            "concept",
            "other",
        }


class TestEntity:
    def test_valid_entity_constructs(self):
        entity = Entity(
            tenant_id="t1",
            name="Alice",
            entity_type=EntityType.PERSON,
        )
        assert entity.tenant_id == "t1"
        assert entity.name == "Alice"
        assert entity.entity_type == EntityType.PERSON

    def test_id_defaults_to_empty(self):
        entity = Entity(tenant_id="t1", name="X", entity_type=EntityType.OTHER)
        assert entity.id == ""

    def test_timestamps_auto_set(self):
        before = datetime.now(UTC)
        entity = Entity(tenant_id="t1", name="X", entity_type=EntityType.OTHER)
        after = datetime.now(UTC)
        assert before <= entity.created_at <= after
        assert before <= entity.updated_at <= after

    def test_aliases_defaults_to_empty_list(self):
        entity = Entity(tenant_id="t1", name="X", entity_type=EntityType.OTHER)
        assert entity.aliases == []

    def test_doc_ids_defaults_to_empty_list(self):
        entity = Entity(tenant_id="t1", name="X", entity_type=EntityType.OTHER)
        assert entity.doc_ids == []

    def test_chunk_ids_defaults_to_empty_list(self):
        entity = Entity(tenant_id="t1", name="X", entity_type=EntityType.OTHER)
        assert entity.chunk_ids == []

    def test_mention_count_defaults_to_zero(self):
        entity = Entity(tenant_id="t1", name="X", entity_type=EntityType.OTHER)
        assert entity.mention_count == 0

    def test_embedding_defaults_to_none(self):
        entity = Entity(tenant_id="t1", name="X", entity_type=EntityType.OTHER)
        assert entity.embedding is None

    def test_metadata_defaults_to_empty_dict(self):
        entity = Entity(tenant_id="t1", name="X", entity_type=EntityType.OTHER)
        assert entity.metadata == {}

    def test_alias_id_round_trips(self):
        """populate_by_name allows using 'id' or '_id'."""
        entity = Entity(
            _id="abc123",
            tenant_id="t1",
            name="X",
            entity_type=EntityType.OTHER,
        )
        assert entity.id == "abc123"
        dumped = entity.model_dump(by_alias=True)
        assert dumped["_id"] == "abc123"


class TestRelationship:
    def test_valid_relationship_constructs(self):
        rel = Relationship(
            tenant_id="t1",
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type="knows",
        )
        assert rel.source_entity_id == "e1"
        assert rel.target_entity_id == "e2"
        assert rel.relation_type == "knows"

    def test_weight_defaults_to_one(self):
        rel = Relationship(
            tenant_id="t1",
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type="knows",
        )
        assert rel.weight == 1.0

    def test_doc_ids_defaults_to_empty_list(self):
        rel = Relationship(
            tenant_id="t1",
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type="knows",
        )
        assert rel.doc_ids == []

    def test_chunk_ids_defaults_to_empty_list(self):
        rel = Relationship(
            tenant_id="t1",
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type="knows",
        )
        assert rel.chunk_ids == []

    def test_description_defaults_to_empty_string(self):
        rel = Relationship(
            tenant_id="t1",
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type="knows",
        )
        assert rel.description == ""


class TestCommunity:
    def test_valid_community_constructs(self):
        comm = Community(tenant_id="t1", level=0)
        assert comm.tenant_id == "t1"
        assert comm.level == 0

    def test_entity_ids_defaults_to_empty_list(self):
        comm = Community(tenant_id="t1", level=0)
        assert comm.entity_ids == []

    def test_parent_community_id_defaults_to_none(self):
        comm = Community(tenant_id="t1", level=0)
        assert comm.parent_community_id is None

    def test_child_community_ids_defaults_to_empty_list(self):
        comm = Community(tenant_id="t1", level=0)
        assert comm.child_community_ids == []

    def test_summary_embedding_defaults_to_none(self):
        comm = Community(tenant_id="t1", level=0)
        assert comm.summary_embedding is None

    def test_title_defaults_to_empty_string(self):
        comm = Community(tenant_id="t1", level=0)
        assert comm.title == ""

    def test_summary_defaults_to_empty_string(self):
        comm = Community(tenant_id="t1", level=0)
        assert comm.summary == ""


class TestGraphConfig:
    def test_graph_rag_enabled_defaults_to_false(self):
        s = Settings()
        assert s.graph_rag_enabled is False

    def test_spacy_model_defaults(self):
        s = Settings()
        assert s.spacy_model == "en_core_web_lg"

    def test_entity_confidence_threshold_defaults(self):
        s = Settings()
        assert s.entity_confidence_threshold == 0.7

    def test_max_entities_per_chunk_defaults(self):
        s = Settings()
        assert s.max_entities_per_chunk == 50
