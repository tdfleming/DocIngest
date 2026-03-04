from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    PENDING = "pending"
    CONVERTING = "converting"
    CONVERTED = "converted"
    CHUNKING = "chunking"
    COMPLETE = "complete"
    FAILED = "failed"


class ContentType(StrEnum):
    PDF = "pdf"
    HTML = "html"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"


class SourceType(StrEnum):
    URL = "url"
    UPLOAD = "upload"
    BATCH = "batch"
    WATCH = "watch"


class DocumentMetadata(BaseModel):
    title: str | None = None
    author: str | None = None
    page_count: int | None = None
    word_count: int = 0
    language: str | None = None


class Document(BaseModel):
    id: str = Field(default="", alias="_id")
    tenant_id: str
    source_hash: str
    source_type: SourceType
    source_ref: str
    content_type: ContentType
    blob_path: str = ""
    file_size_bytes: int = 0
    markdown_blob_path: str = ""
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    status: DocumentStatus = DocumentStatus.PENDING
    error: str | None = None
    error_type: str | None = None
    error_stage: str | None = None
    chunk_count: int = 0
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None

    model_config = {"populate_by_name": True}
