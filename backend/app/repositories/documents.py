"""Document persistence: CRUD + lifecycle status transitions.

No business logic here — e.g. this module does not know what "processing"
entails; the ingestion service (Phase 3) drives the transitions.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document

VALID_STATUSES = frozenset({"pending", "processing", "processed", "failed"})


class DocumentRepository:
    """Data access for the ``documents`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        filename: str,
        original_name: str,
        file_size: int,
        mime_type: str = "application/pdf",
        doc_metadata: dict | None = None,
        sha256: str | None = None,
        document_id: uuid.UUID | None = None,
    ) -> Document:
        """Insert a new document row in ``pending`` status. Flushes; caller commits."""
        doc = Document(
            filename=filename,
            original_name=original_name,
            mime_type=mime_type,
            file_size=file_size,
            doc_metadata=doc_metadata or {},
            sha256=sha256,
        )
        if document_id is not None:
            doc.id = document_id
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def get(self, document_id: uuid.UUID) -> Document | None:
        return await self._session.get(Document, document_id)

    async def find_by_sha256(self, sha256: str) -> Document | None:
        """Find a document by its content hash (duplicate detection)."""
        return (
            (
                await self._session.execute(
                    select(Document).where(Document.sha256 == sha256)
                )
            )
            .scalars()
            .first()
        )

    async def list(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Document], int]:
        """Newest-first paginated list. Returns (items, total)."""
        if page < 1 or size < 1 or size > 100:
            raise ValueError("page must be >= 1 and 1 <= size <= 100")
        if status is not None and status not in VALID_STATUSES:
            raise ValueError(f"unknown status: {status!r}")

        stmt = select(Document).order_by(Document.created_at.desc())
        count_stmt = select(func.count()).select_from(Document)
        if status is not None:
            stmt = stmt.where(Document.status == status)
            count_stmt = count_stmt.where(Document.status == status)

        total = (await self._session.execute(count_stmt)).scalar_one()
        items = (
            (await self._session.execute(stmt.offset((page - 1) * size).limit(size)))
            .scalars()
            .all()
        )
        return list(items), total

    async def update_status(
        self,
        document_id: uuid.UUID,
        status: str,
        *,
        page_count: int | None = None,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> Document | None:
        """Transition a document's lifecycle status. Returns None if missing."""
        if status not in VALID_STATUSES:
            raise ValueError(f"unknown status: {status!r}")
        doc = await self.get(document_id)
        if doc is None:
            return None
        doc.status = status
        if page_count is not None:
            doc.page_count = page_count
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        doc.error_message = error_message
        await self._session.flush()
        return doc

    async def delete(self, document_id: uuid.UUID) -> bool:
        """Delete a document; its chunks cascade. Returns False if missing."""
        doc = await self.get(document_id)
        if doc is None:
            return False
        await self._session.delete(doc)  # chunks removed via ON DELETE CASCADE
        await self._session.flush()
        return True

    async def count(self, *, status: str | None = None) -> int:
        stmt = select(func.count()).select_from(Document)
        if status is not None:
            if status not in VALID_STATUSES:
                raise ValueError(f"unknown status: {status!r}")
            stmt = stmt.where(Document.status == status)
        return (await self._session.execute(stmt)).scalar_one()
