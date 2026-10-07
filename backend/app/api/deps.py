"""Shared FastAPI dependencies."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.services import (
    DoclingHybridChunker,
    DoclingProcessor,
    GroqLLMProvider,
    IngestionService,
    MiniLMEmbeddingProvider,
    RAGService,
    StorageService,
)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a DB session from the lifespan-managed session factory."""
    async with request.app.state.session_factory() as session:
        yield session


def get_app_settings() -> Settings:
    return get_settings()


def get_ingestion_service(request: Request) -> IngestionService:
    """Build the ingestion service from lifespan-managed singletons.

    The heavy ML pieces (Docling converter, embedding model) are created once
    in the lifespan and shared; the service itself is cheap to construct.
    """
    settings = get_settings()
    return IngestionService(
        settings=settings,
        storage=StorageService(settings.upload_dir),
        docling_processor=request.app.state.docling_processor,
        chunker=request.app.state.chunker,
        embedder=request.app.state.embedder,
        session_factory=request.app.state.session_factory,
    )


def get_rag_service(request: Request) -> RAGService:
    """Build the RAG service from lifespan-managed singletons.

    ``app.state.llm`` is None when GROQ_API_KEY is unset — the service then
    fails fast with 503 instead of halfway through retrieval.
    """
    settings = get_settings()
    return RAGService(
        settings=settings,
        embedder=request.app.state.embedder,
        llm=request.app.state.llm,
        session_factory=request.app.state.session_factory,
    )


# Re-exported for tests that build services directly.
__all__ = [
    "DoclingHybridChunker",
    "DoclingProcessor",
    "GroqLLMProvider",
    "IngestionService",
    "MiniLMEmbeddingProvider",
    "RAGService",
    "StorageService",
    "get_app_settings",
    "get_ingestion_service",
    "get_rag_service",
    "get_session",
]
