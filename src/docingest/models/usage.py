"""Usage metering models."""

from enum import StrEnum

from pydantic import BaseModel


class UsageEventType(StrEnum):
    INGEST = "ingest"  # a document accepted for ingestion
    SEARCH = "search"  # a search query
    GRAPH_BUILD = "graph_build"  # a graph build job


class UsageSummary(BaseModel):
    period_start: str
    events: dict[str, int]
