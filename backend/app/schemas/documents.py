"""Pydantic DTOs for the documents API.

Deliberately excludes internal details: no filesystem paths, no SHA-256,
no embedding vectors. The frontend only ever sees metadata + status.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_name: str
    mime_type: str
    file_size: int
    page_count: int | None
    chunk_count: int
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    size: int


class UploadResponse(BaseModel):
    documents: list[DocumentOut]
