"""Unit tests for upload validation and file storage."""

import io
import uuid

import pytest
from fastapi import UploadFile

from app.core.errors import AppError
from app.services.storage import (
    DuplicateDocumentError,
    StorageService,
    UploadTooLargeError,
    read_limited,
    validate_pdf_bytes,
)
from tests.factories import make_encrypted_pdf, make_test_pdf

MAX_BYTES = 1024 * 1024


def test_validate_accepts_real_pdf():
    _, data = make_test_pdf("T", [("H", "body text here")])
    uploaded = validate_pdf_bytes(data, "paper.pdf", MAX_BYTES)
    assert uploaded.original_name == "paper.pdf"
    assert uploaded.mime_type == "application/pdf"
    assert uploaded.size == len(data)
    assert len(uploaded.sha256) == 64


def test_validate_rejects_non_pdf():
    with pytest.raises(AppError) as exc_info:
        validate_pdf_bytes(b"definitely not a pdf", "evil.pdf", MAX_BYTES)
    assert exc_info.value.code == "INVALID_FILE_TYPE"


def test_validate_rejects_wrong_extension_but_pdf_bytes():
    _, data = make_test_pdf("T", [("H", "body")])
    with pytest.raises(AppError) as exc_info:
        validate_pdf_bytes(data, "paper.txt", MAX_BYTES)
    assert exc_info.value.code == "INVALID_FILE_TYPE"


def test_validate_rejects_empty_file():
    with pytest.raises(AppError) as exc_info:
        validate_pdf_bytes(b"", "empty.pdf", MAX_BYTES)
    assert exc_info.value.code == "EMPTY_FILE"


def test_validate_rejects_oversized():
    _, data = make_test_pdf("T", [("H", "body")])
    with pytest.raises(UploadTooLargeError):
        validate_pdf_bytes(data, "big.pdf", max_bytes=10)


def test_validate_rejects_encrypted_pdf():
    data = make_encrypted_pdf()
    assert data.startswith(b"%PDF-")  # it *looks* like a PDF…
    with pytest.raises(AppError) as exc_info:
        validate_pdf_bytes(data, "secret.pdf", MAX_BYTES)
    assert exc_info.value.code == "ENCRYPTED_PDF"  # …but is rejected


async def test_read_limited_enforces_cap_while_streaming():
    upload = UploadFile(file=io.BytesIO(b"x" * 100), filename="a.pdf")
    with pytest.raises(UploadTooLargeError):
        await read_limited(upload, max_bytes=10)


async def test_read_limited_reads_small_file():
    upload = UploadFile(file=io.BytesIO(b"hello"), filename="a.pdf")
    assert await read_limited(upload, max_bytes=10) == b"hello"


def test_storage_save_and_delete_roundtrip(tmp_path):
    storage = StorageService(tmp_path / "uploads")
    doc_id = uuid.uuid4()
    path = storage.save(doc_id, b"%PDF- fake")
    assert path.exists() and path.name == f"{doc_id}.pdf"
    storage.delete(doc_id)
    assert not path.exists()
    storage.delete(doc_id)  # idempotent, no raise


def test_duplicate_error_carries_document_id():
    doc_id = uuid.uuid4()
    err = DuplicateDocumentError(doc_id)
    assert err.status_code == 409
    assert err.code == "DUPLICATE_DOCUMENT"
    assert err.details == {"document_id": str(doc_id)}
