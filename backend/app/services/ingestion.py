"""Ingestion orchestration: upload → validate → process → store.

Lifecycle of a document row:
    pending → processing → processed
                        ↘ failed (with a user-safe ``error_message``)

A ``failed`` document can be retried via :meth:`retry_failed`; nothing about
a failure corrupts the database — chunk inserts and the status flip happen
in a single transaction, and file writes are atomic (temp + rename).

The service never touches HTTP: the API layer calls ``submit_uploads`` /
``retry_failed`` synchronously and ``process_document`` via BackgroundTasks.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

import anyio
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import NotFoundError, ValidationError
from app.db.models import Document
from app.repositories import ChunkCreate, ChunkRepository, DocumentRepository
from app.repositories.documents import VALID_STATUSES  # noqa: F401  (re-export)
from app.services.chunking import Chunker
from app.services.docling_processor import DoclingConversionError, DoclingProcessor
from app.services.embeddings import EmbeddingProvider
from app.services.storage import (
    DuplicateDocumentError,
    StorageService,
    read_limited,
    validate_pdf_bytes,
)

logger = logging.getLogger("vectorbrain.ingestion")


def _log_timing(label: str, start: float, extra: str = "") -> float:
    """Log elapsed time since start and return new timestamp."""
    elapsed = time.perf_counter() - start
    logger.info("timing: %s took %.3fs %s", label, elapsed, extra)
    return time.perf_counter()


class IngestionService:
    """Coordinates the whole ingestion pipeline."""

    def __init__(
        self,
        *,
        settings,
        storage: StorageService,
        docling_processor: DoclingProcessor,
        chunker: Chunker,
        embedder: EmbeddingProvider,
        session_factory: async_sessionmaker,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._docling = docling_processor
        self._chunker = chunker
        self._embedder = embedder
        self._session_factory = session_factory
        self._max_bytes = settings.max_file_mb * 1024 * 1024

    # ── Request-time API ──────────────────────────────────────────────

    async def submit_uploads(
        self, session: AsyncSession, files: list[UploadFile]
    ) -> list[Document]:
        """Validate uploads, persist files, create ``pending`` rows.

        Uses the caller's session; the caller commits. Raises
        ``ValidationError`` / ``UploadTooLargeError`` / ``DuplicateDocumentError``.
        """
        if not files:
            raise ValidationError("No files were uploaded.", code="EMPTY_UPLOAD")
        if len(files) > self._settings.max_files_per_request:
            raise ValidationError(
                f"At most {self._settings.max_files_per_request} files per request.",
                code="TOO_MANY_FILES",
            )

        docs_repo = DocumentRepository(session)
        documents: list[Document] = []
        saved_ids: list[uuid.UUID] = []
        try:
            for upload in files:
                data = await read_limited(upload, self._max_bytes)
                validated = validate_pdf_bytes(
                    data, upload.filename or "", self._max_bytes
                )

                existing = await docs_repo.find_by_sha256(validated.sha256)
                if existing is not None:
                    raise DuplicateDocumentError(existing.id)

                document_id = uuid.uuid4()
                stored_path = self._storage.save(document_id, validated.data)
                saved_ids.append(document_id)
                doc = await docs_repo.create(
                    document_id=document_id,
                    filename=stored_path.name,
                    original_name=validated.original_name,
                    file_size=validated.size,
                    sha256=validated.sha256,
                )
                documents.append(doc)
                logger.info(
                    "upload accepted: %s (%d bytes, sha256=%s…)",
                    validated.original_name,
                    validated.size,
                    validated.sha256[:12],
                )
        except Exception:
            # Don't leak orphan files when validation/dedupe aborts the batch.
            for saved_id in saved_ids:
                self._storage.delete(saved_id)
            raise
        return documents

    def enqueue(
        self, background_tasks: BackgroundTasks, document_ids: list[uuid.UUID]
    ) -> None:
        for document_id in document_ids:
            background_tasks.add_task(self.process_document, document_id)

    async def retry_failed(
        self, session: AsyncSession, document_id: uuid.UUID
    ) -> Document:
        """Reset a ``failed`` document to ``pending`` so it can be reprocessed."""
        docs_repo = DocumentRepository(session)
        doc = await docs_repo.get(document_id)
        if doc is None:
            raise NotFoundError(f"Document {document_id} not found.")
        if doc.status != "failed":
            raise ValidationError(
                f"Only failed documents can be retried (status is {doc.status}).",
                code="INVALID_RETRY_STATE",
            )
        updated = await docs_repo.update_status(
            document_id, "pending", error_message=None
        )
        assert updated is not None
        return updated

    async def delete_document(
        self, session: AsyncSession, document_id: uuid.UUID
    ) -> bool:
        """Delete a document row (chunks cascade) and its uploaded file."""
        deleted = await DocumentRepository(session).delete(document_id)
        if deleted:
            self._storage.delete(document_id)
        return deleted

    # ── Background pipeline ───────────────────────────────────────────

    async def process_document(self, document_id: uuid.UUID) -> None:
        """Run the full pipeline for one document. Never raises."""
        async with self._session_factory() as session:
            docs_repo = DocumentRepository(session)
            doc = await docs_repo.get(document_id)
            if doc is None:
                logger.error("process_document: %s not found", document_id)
                return
            if doc.status not in ("pending", "processing"):
                logger.info(
                    "process_document: %s already %s, skipping",
                    document_id,
                    doc.status,
                )
                return

            await docs_repo.update_status(document_id, "processing")
            await session.commit()

            try:
                chunks, page_count = await self._run_pipeline(doc)
                chunks_repo = ChunkRepository(session)
                await chunks_repo.bulk_create(chunks)
                await docs_repo.update_status(
                    document_id,
                    "processed",
                    page_count=page_count,
                    chunk_count=len(chunks),
                )
                await session.commit()
                logger.info(
                    "ingested %s: %d pages, %d chunks",
                    doc.original_name,
                    page_count,
                    len(chunks),
                )
            except Exception as exc:  # noqa: BLE001 — failure must be recorded
                await session.rollback()
                message = self._sanitize_error(exc, doc)
                logger.exception("ingestion failed for %s", doc.original_name)
                # Fresh status write after rollback.
                await DocumentRepository(session).update_status(
                    document_id, "failed", error_message=message
                )
                await session.commit()

    async def _run_pipeline(self, doc: Document) -> tuple[list[ChunkCreate], int]:
        """Docling → chunk → embed. CPU-bound steps run in a threadpool."""
        pdf_path = self._storage.path_for(doc.id)
        if not pdf_path.exists():
            raise DoclingConversionError(
                f"Could not process {doc.original_name}: uploaded file is missing."
            )

        t0 = time.perf_counter()
        t0 = _log_timing("pipeline_start", t0, f"doc={doc.original_name}")

        dl_doc = await anyio.to_thread.run_sync(self._docling.convert, pdf_path)
        t0 = _log_timing("docling_convert", t0, f"pages={self._docling.page_count(dl_doc)}")

        text_chunks = await anyio.to_thread.run_sync(self._chunker.chunk, dl_doc)
        t0 = _log_timing("chunking", t0, f"chunks={len(text_chunks)}")

        if not text_chunks:
            raise DoclingConversionError(
                f"Could not process {doc.original_name}: no searchable text found."
            )

        embeddings = await anyio.to_thread.run_sync(
            self._embedder.embed, [c.text for c in text_chunks]
        )
        t0 = _log_timing("embedding", t0, f"vectors={len(embeddings)}")

        if len(embeddings) != len(text_chunks):
            raise RuntimeError("embedder returned a mismatched number of vectors")

        chunk_rows = [
            ChunkCreate(
                document_id=doc.id,
                chunk_index=i,
                content=chunk.text,
                token_count=chunk.token_count,
                embedding=embeddings[i],
                page_numbers=chunk.page_numbers,
                heading_path=chunk.heading_path,
            )
            for i, chunk in enumerate(text_chunks)
        ]
        t0 = _log_timing("chunk_row_creation", t0)
        _log_timing("pipeline_total", t0, f"doc={doc.original_name}")
        return chunk_rows, self._docling.page_count(dl_doc)

    def _sanitize_error(self, exc: Exception, doc: Document) -> str:
        """User-safe failure message: no internal paths, bounded length."""
        message = str(exc) or type(exc).__name__
        upload_dir = str(Path(self._storage.path_for(doc.id)).parent)
        message = message.replace(upload_dir, "<uploads>")
        message = message.replace(str(doc.id), "<document>")
        return message[:500]
