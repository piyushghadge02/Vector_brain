"""Central application configuration.

Every setting is driven by environment variables (12-factor). Copy
``backend/.env.example`` to ``backend/.env`` for local development.
``.env`` is gitignored — real secrets must never be committed.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="VectorBrain")
    env: str = Field(default="dev", description="dev | prod | test")
    log_level: str = Field(default="INFO")

    database_url: str = Field(
        default="postgresql+asyncpg://vectorbrain:vectorbrain@localhost:5432/vectorbrain",
        description="Async SQLAlchemy URL for PostgreSQL + pgvector",
    )

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # ── Phase 2 — document ingestion (placeholders until implemented) ──
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    upload_dir: str = Field(default="/data/uploads")
    max_file_mb: int = Field(default=50)
    max_files_per_request: int = Field(default=10)
    chunk_max_tokens: int = Field(default=512)

    # ── Phase 4 — RAG / Groq ─────────────────────────────────────────
    groq_api_key: str | None = Field(default=None)
    groq_model: str = Field(default="openai/gpt-oss-120b")
    groq_timeout_seconds: float = Field(default=60.0)
    retrieval_top_k: int = Field(default=8)
    rag_max_context_tokens: int = Field(default=6000)
    llm_max_tokens: int = Field(default=1024)
    llm_temperature: float = Field(default=0.2)

    rate_limit_query_per_min: int = Field(default=20)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — import this, never instantiate directly."""
    return Settings()
