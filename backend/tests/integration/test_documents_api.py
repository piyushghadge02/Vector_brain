"""Integration tests for the documents API (upload/list/get/retry/delete).

The ML pipeline is stubbed via dependency injection — these tests verify
HTTP behavior, validation, deduplication, status transitions, and the
background-task wiring without downloading any models. The real Docling +
MiniLM pipeline is covered by ``test_ingestion_e2e.py`` (real_model).
"""

import os
import time
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.deps import get_ingestion_service
from app.config import get_settings
from app.db.session import create_engine, create_session_factory
from app.services import (
    Chunker,
    DoclingConversionError,
    EmbeddingProvider,
    IngestionService,
    StorageService,
    TextChunk,
)
from tests.factories import make_test_pdf

API = "/api/v1/documents"


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Truncate all tables before each test — tests are order-independent."""
    engine = create_engine(os.environ["DATABASE_URL"])
    factory = create_session_factory(engine)
    async with factory() as session:
        await session.execute(
            text("TRUNCATE documents, chunks, conversations, messages CASCADE")
        )
        await session.commit()
    await engine.dispose()


# ── Stubs ─────────────────────────────────────────────────────────────


class FakeDoc:
    pages = [1, 2]


class StubDoclingProcessor:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def convert(self, pdf_path):
        if self.fail:
            raise DoclingConversionError("stub conversion boom")
        return FakeDoc()

    @staticmethod
    def page_count(document) -> int:
        return 2


class StubChunker(Chunker):
    def chunk(self, document) -> list[TextChunk]:
        return [
            TextChunk(
                text="first stub chunk",
                page_numbers=[1],
                heading_path="Intro",
                token_count=3,
            ),
            TextChunk(
                text="second stub chunk",
                page_numbers=[2],
                heading_path="Intro",
                token_count=3,
            ),
        ]


class StubEmbedder(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0 if j == i % 384 else 0.0 for j in range(384)]
            for i in range(len(texts))
        ]


@pytest.fixture
def stub_service_factory(client: TestClient, tmp_path):
    """Build IngestionService instances with a stubbed ML pipeline."""
    upload_dir = tmp_path / "uploads"

    def _make(fail: bool = False) -> IngestionService:
        return IngestionService(
            settings=get_settings(),
            storage=StorageService(upload_dir),
            docling_processor=StubDoclingProcessor(fail=fail),
            chunker=StubChunker(),
            embedder=StubEmbedder(),
            session_factory=client.app.state.session_factory,
        )

    _make.upload_dir = upload_dir
    return _make


@pytest.fixture
def stub_service(stub_service_factory, client: TestClient):
    service = stub_service_factory(fail=False)
    client.app.dependency_overrides[get_ingestion_service] = lambda: service
    yield service
    client.app.dependency_overrides.clear()


def upload(client: TestClient, pdfs: list[tuple[str, bytes]]):
    files = [("files", (name, data, "application/pdf")) for name, data in pdfs]
    return client.post(f"{API}/upload", files=files)


def wait_for_status(client: TestClient, doc_id: str, wanted: str, timeout: int = 60):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(f"{API}/{doc_id}").json()
        if last["status"] == wanted:
            return last
        time.sleep(0.5)
    raise TimeoutError(f"document {doc_id} never reached {wanted}; last={last}")


def sample_pdf(name: str = "sample.pdf") -> tuple[str, bytes]:
    return make_test_pdf(
        "Sample Research", [("Intro", "Body text " * 30)], filename=name
    )


# ── Upload & processing ───────────────────────────────────────────────


@pytest.mark.integration
def test_upload_multiple_pdfs_and_process(
    client: TestClient, stub_service, stub_service_factory
):
    pdfs = [sample_pdf("a.pdf"), sample_pdf("b.pdf")]
    resp = upload(client, pdfs)
    assert resp.status_code == 202, resp.text
    docs = resp.json()["documents"]
    assert len(docs) == 2
    assert {d["original_name"] for d in docs} == {"a.pdf", "b.pdf"}
    assert all(d["status"] == "pending" for d in docs)

    # No internal details leak to the frontend.
    for d in docs:
        assert "filename" not in d and "sha256" not in d
        assert "uploads" not in str(d).lower()

    for d in docs:
        final = wait_for_status(client, d["id"], "processed")
        assert final["chunk_count"] == 2
        assert final["page_count"] == 2
        assert final["error_message"] is None

    # Files landed on disk under the isolated upload dir.
    stored = list(Path(stub_service_factory.upload_dir).glob("*.pdf"))
    assert len(stored) == 2


@pytest.mark.integration
def test_upload_rejects_non_pdf(client: TestClient, stub_service):
    resp = client.post(
        f"{API}/upload",
        files=[("files", ("evil.pdf", b"not a pdf at all", "application/pdf"))],
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_FILE_TYPE"


@pytest.mark.integration
def test_upload_rejects_too_many_files(client: TestClient, stub_service):
    pdfs = [sample_pdf(f"f{i}.pdf") for i in range(11)]
    resp = upload(client, pdfs)
    assert resp.status_code == 422
    assert resp.json()["code"] == "TOO_MANY_FILES"


@pytest.mark.integration
def test_upload_duplicate_returns_409(client: TestClient, stub_service):
    pdf = sample_pdf("dup.pdf")
    first = upload(client, [pdf])
    assert first.status_code == 202
    first_id = first.json()["documents"][0]["id"]

    second = upload(client, [pdf])
    assert second.status_code == 409
    body = second.json()
    assert body["code"] == "DUPLICATE_DOCUMENT"
    assert body["details"]["document_id"] == first_id


# ── List / get ────────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_and_get_documents(client: TestClient, stub_service):
    upload(client, [sample_pdf("one.pdf"), sample_pdf("two.pdf")])

    listing = client.get(API).json()
    assert listing["total"] == 2
    assert len(listing["items"]) == 2

    doc_id = listing["items"][0]["id"]
    fetched = client.get(f"{API}/{doc_id}").json()
    assert fetched["original_name"] in {"one.pdf", "two.pdf"}

    missing = client.get(f"{API}/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"


# ── Delete ────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_delete_document_removes_everything(
    client: TestClient, stub_service, stub_service_factory
):
    doc_id = upload(client, [sample_pdf("gone.pdf")]).json()["documents"][0]["id"]
    wait_for_status(client, doc_id, "processed")

    assert client.delete(f"{API}/{doc_id}").status_code == 204
    assert client.get(f"{API}/{doc_id}").status_code == 404
    assert client.delete(f"{API}/{doc_id}").status_code == 404  # idempotent-ish
    assert list(Path(stub_service_factory.upload_dir).glob("*.pdf")) == []


# ── Retry ─────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_failed_document_can_be_retried(client: TestClient, stub_service_factory):
    app = client.app
    app.dependency_overrides[get_ingestion_service] = lambda: stub_service_factory(
        fail=True
    )
    try:
        doc_id = upload(client, [sample_pdf("flaky.pdf")]).json()["documents"][0]["id"]
        failed = wait_for_status(client, doc_id, "failed")
        assert "stub conversion boom" in failed["error_message"]
        assert failed["chunk_count"] == 0

        # Retry with a healthy pipeline.
        app.dependency_overrides[get_ingestion_service] = lambda: (
            stub_service_factory(fail=False)
        )
        resp = client.post(f"{API}/{doc_id}/retry")
        assert resp.status_code == 202, resp.text
        assert resp.json()["status"] == "pending"

        final = wait_for_status(client, doc_id, "processed")
        assert final["chunk_count"] == 2
        assert final["error_message"] is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_retry_rejected_for_non_failed(client: TestClient, stub_service):
    doc_id = upload(client, [sample_pdf("ok.pdf")]).json()["documents"][0]["id"]
    wait_for_status(client, doc_id, "processed")

    resp = client.post(f"{API}/{doc_id}/retry")
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_RETRY_STATE"

    assert client.post(f"{API}/{uuid.uuid4()}/retry").status_code == 404
