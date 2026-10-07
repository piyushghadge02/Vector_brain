"""Upload validation + file persistence.

Security rules:
- Only PDFs, verified by magic bytes (``%PDF-``), not just the extension.
- Size is enforced while streaming — a huge upload can never fill memory.
- Encrypted/password-protected PDFs are rejected with a clear message.
- Stored under ``{upload_dir}/{document_id}.pdf``; the original filename is
  kept in the database only. Internal paths are never exposed via the API.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import AppError, ValidationError

logger = logging.getLogger("vectorbrain.storage")

PDF_MAGIC = b"%PDF-"
READ_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class UploadTooLargeError(AppError):
    code = "UPLOAD_TOO_LARGE"
    message = "File exceeds the maximum allowed size."
    status_code = 413


class DuplicateDocumentError(AppError):
    code = "DUPLICATE_DOCUMENT"
    message = "This file has already been uploaded."
    status_code = 409

    def __init__(self, document_id: uuid.UUID) -> None:
        super().__init__(details={"document_id": str(document_id)})


@dataclass(frozen=True)
class UploadedFile:
    """A validated upload, ready to persist."""

    original_name: str
    mime_type: str
    size: int
    sha256: str
    data: bytes


def _is_encrypted_pdf(data: bytes) -> bool:
    """Detect password-protected PDFs.

    Uses pypdf when available; falls back to a trailer heuristic. Either
    way this is only a validation gate — never a security boundary.
    """
    try:
        from pypdf import PdfReader

        import io

        return PdfReader(io.BytesIO(data)).is_encrypted
    except ImportError:  # pragma: no cover — pypdf is a real dependency
        return b"/Encrypt" in data
    except Exception:
        # Unparseable here means Docling will fail later with a clean
        # ingestion error; don't block the upload on a broken heuristic.
        return False


async def read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an upload stream, aborting as soon as it exceeds ``max_bytes``."""
    pieces: list[bytes] = []
    total = 0
    while True:
        piece = await upload.read(READ_CHUNK_SIZE)
        if not piece:
            break
        total += len(piece)
        if total > max_bytes:
            raise UploadTooLargeError(
                f"File exceeds the {max_bytes // (1024 * 1024)} MB limit."
            )
        pieces.append(piece)
    return b"".join(pieces)


def validate_pdf_bytes(data: bytes, filename: str, max_bytes: int) -> UploadedFile:
    """Validate raw bytes as an ingestible PDF. Raises AppError on violation."""
    if not data:
        raise ValidationError("Uploaded file is empty.", code="EMPTY_FILE")
    if len(data) > max_bytes:  # defensive; read_limited normally catches first
        raise UploadTooLargeError()
    name = (filename or "upload.pdf").strip() or "upload.pdf"
    if not name.lower().endswith(".pdf") or not data.startswith(PDF_MAGIC):
        raise ValidationError(f"{name!r} is not a PDF file.", code="INVALID_FILE_TYPE")
    if _is_encrypted_pdf(data):
        raise ValidationError(
            f"{name!r} is password-protected; encrypted PDFs are not supported.",
            code="ENCRYPTED_PDF",
        )
    return UploadedFile(
        original_name=name,
        mime_type="application/pdf",
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        data=data,
    )


class StorageService:
    """Persists validated uploads to the local upload directory."""

    def __init__(self, upload_dir: str | Path) -> None:
        self._dir = Path(upload_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, document_id: uuid.UUID) -> Path:
        return self._dir / f"{document_id}.pdf"

    def save(self, document_id: uuid.UUID, data: bytes) -> Path:
        """Write bytes atomically (temp file + rename). Returns the path."""
        target = self.path_for(document_id)
        tmp = target.with_suffix(".pdf.tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
        return target

    def delete(self, document_id: uuid.UUID) -> None:
        """Best-effort file removal; logs instead of raising."""
        try:
            self.path_for(document_id).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("could not delete upload file for %s: %s", document_id, exc)
