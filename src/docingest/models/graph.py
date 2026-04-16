from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    EVENT = "event"
    PRODUCT = "product"
    CONCEPT = "concept"
    OTHER = "other"


class Entity(BaseModel):
    id: str = Field(default="", alias="_id")
    tenant_id: str
    name: str
    entity_type: EntityType
    aliases: list[str] = Field(default_factory=list)
    doc_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    mention_count: int = 0
    embedding: list[float] | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"populate_by_name": True}


class Relationship(BaseModel):
    id: str = Field(default="", alias="_id")
    tenant_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    description: str = ""
    weight: float = 1.0
    doc_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"populate_by_name": True}


class Community(BaseModel):
    id: str = Field(default="", alias="_id")
    tenant_id: str
    level: int
    title: str = ""
    summary: str = ""
    entity_ids: list[str] = Field(default_factory=list)
    parent_community_id: str | None = None
    child_community_ids: list[str] = Field(default_factory=list)
    summary_embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"populate_by_name": True}
