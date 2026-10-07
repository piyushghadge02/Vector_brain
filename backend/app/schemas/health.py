"""Pydantic DTOs for the health endpoint."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="ok | degraded")
    service: str
    env: str
    database: str = Field(description="connected | unreachable")
    pgvector: str = Field(description="available | missing")
    embeddings: str = Field(description="embedding model load state")
    groq_configured: bool = Field(
        description="whether GROQ_API_KEY is set (value never exposed)"
    )
