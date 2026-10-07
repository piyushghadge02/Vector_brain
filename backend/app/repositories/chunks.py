"""Chunk persistence + pgvector semantic search.

Embeddings are 384-dimensional and L2-normalized (enforced by the
``vector(384)`` column and the embedding provider respectively), so
cosine distance (``<=>``) gives the correct ranking.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document

EMBEDDING_DIM = 384


@dataclass(frozen=True)
class ChunkCreate:
    """Input for inserting one chunk."""

    document_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    embedding: list[float]
    page_numbers: list[int] | None = None
    heading_path: str = ""


@dataclass(frozen=True)
class ChunkSearchResult:
    """One hit from :meth:`ChunkRepository.vector_search`."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    content: str
    page_numbers: list[int]
    heading_path: str
    similarity: float  # 1 - cosine_distance, in [-1, 1]


class ChunkRepository:
    """Data access for the ``chunks`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(self, items: list[ChunkCreate]) -> list[Chunk]:
        """Insert many chunks efficiently. Flushes; caller commits."""
        chunks = [
            Chunk(
                document_id=item.document_id,
                chunk_index=item.chunk_index,
                content=item.content,
                page_numbers=item.page_numbers or [],
                heading_path=item.heading_path,
                token_count=item.token_count,
                embedding=item.embedding,
            )
            for item in items
        ]
        self._session.add_all(chunks)
        await self._session.flush()
        return chunks

    async def list_by_document(
        self,
        document_id: uuid.UUID,
        *,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[Chunk], int]:
        """Chunks of one document, in chunk order. Returns (items, total)."""
        if page < 1 or size < 1 or size > 500:
            raise ValueError("page must be >= 1 and 1 <= size <= 500")
        base = select(Chunk).where(Chunk.document_id == document_id)
        total = (
            await self._session.execute(
                select(func.count())
                .select_from(Chunk)
                .where(Chunk.document_id == document_id)
            )
        ).scalar_one()
        items = (
            (
                await self._session.execute(
                    base.order_by(Chunk.chunk_index)
                    .offset((page - 1) * size)
                    .limit(size)
                )
            )
            .scalars()
            .all()
        )
        return list(items), total

    async def count_by_document(self, document_id: uuid.UUID) -> int:
        return (
            await self._session.execute(
                select(func.count())
                .select_from(Chunk)
                .where(Chunk.document_id == document_id)
            )
        ).scalar_one()

    async def delete_by_document(self, document_id: uuid.UUID) -> int:
        """Delete all chunks of a document. Returns the number removed."""
        result = await self._session.execute(
            Chunk.__table__.delete().where(Chunk.document_id == document_id)
        )
        await self._session.flush()
        return result.rowcount

    async def vector_search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 8,
        document_ids: list[uuid.UUID] | None = None,
        min_similarity: float | None = None,
    ) -> list[ChunkSearchResult]:
        """Semantic search over **processed** documents' chunks.

        - ``document_ids=None`` (or empty) searches the whole corpus —
          the "query all documents" behavior.
        - Results are ordered by cosine similarity, descending.
        """
        if len(query_vector) != EMBEDDING_DIM:
            raise ValueError(
                f"query_vector must have {EMBEDDING_DIM} dimensions, "
                f"got {len(query_vector)}"
            )
        if not 1 <= top_k <= 100:
            raise ValueError("top_k must be between 1 and 100")

        distance = Chunk.embedding.cosine_distance(query_vector)
        similarity = (1 - distance).label("similarity")

        stmt = (
            select(Chunk, Document.original_name, similarity)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.status == "processed")
        )
        if document_ids:
            stmt = stmt.where(Chunk.document_id.in_(document_ids))
        if min_similarity is not None:
            stmt = stmt.where(
                (1 - Chunk.embedding.cosine_distance(query_vector)) >= min_similarity
            )
        stmt = stmt.order_by(distance).limit(top_k)

        rows = (await self._session.execute(stmt)).all()
        return [
            ChunkSearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=original_name,
                content=chunk.content,
                page_numbers=list(chunk.page_numbers or []),
                heading_path=chunk.heading_path,
                similarity=float(similarity_value),
            )
            for chunk, original_name, similarity_value in rows
        ]
