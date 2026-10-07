"""Pydantic DTOs for the chat/RAG API.

The Groq API key never appears here — it lives server-side only.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_ids: list[UUID] | None = Field(
        default=None,
        description="Scope the search to these documents. "
        "Omitted/empty = search ALL processed documents.",
    )
    top_k: int = Field(default=8, ge=1, le=20)


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    filename: str  # user-facing original file name
    chunk_id: UUID
    pages: list[int]
    heading: str
    snippet: str
    similarity: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    model: str
    latency_ms: int
