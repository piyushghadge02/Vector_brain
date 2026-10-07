"""Service layer — business logic.

Services orchestrate repositories, file storage, and ML providers.
They never touch HTTP; the API layer calls them.
"""

from app.services.chunking import Chunker, DoclingHybridChunker, TextChunk
from app.services.docling_processor import DoclingConversionError, DoclingProcessor
from app.services.embeddings import EmbeddingProvider, MiniLMEmbeddingProvider
from app.services.groq_client import (
    GroqLLMProvider,
    LLMNotConfiguredError,
    LLMProvider,
    LLMUpstreamError,
)
from app.services.ingestion import IngestionService
from app.services.rag import (
    CitedSource,
    QueryResult,
    RAGService,
    build_context,
    build_user_prompt,
    extract_citations,
)
from app.services.storage import (
    DuplicateDocumentError,
    StorageService,
    UploadedFile,
    UploadTooLargeError,
)

__all__ = [
    "Chunker",
    "CitedSource",
    "DoclingConversionError",
    "DoclingHybridChunker",
    "DoclingProcessor",
    "DuplicateDocumentError",
    "EmbeddingProvider",
    "GroqLLMProvider",
    "LLMNotConfiguredError",
    "LLMProvider",
    "LLMUpstreamError",
    "MiniLMEmbeddingProvider",
    "IngestionService",
    "QueryResult",
    "RAGService",
    "StorageService",
    "TextChunk",
    "UploadTooLargeError",
    "UploadedFile",
    "build_context",
    "build_user_prompt",
    "extract_citations",
]
