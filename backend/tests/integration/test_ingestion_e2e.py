"""End-to-end ingestion with the REAL pipeline (Docling + MiniLM).

Marked ``real_model``: downloads ~100 MB of models on first run and takes
several minutes. Always run locally for verification; skipped in CI::

    no_proxy=localhost,127.0.0.1 NO_PROXY=localhost,127.0.0.1 \\
    DATABASE_URL=postgresql+asyncpg://vectorbrain:vectorbrain@localhost:5432/vectorbrain_test \\
    pytest -m real_model tests/integration/test_ingestion_e2e.py

(The no_proxy override works around an httpx parsing quirk with bracketed
IPv6 entries in this sandbox's proxy config; it is not needed in CI/prod.)
"""

import asyncio
import os
import time
import uuid

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import create_engine, create_session_factory
from app.repositories import ChunkRepository, DocumentRepository

pytestmark = pytest.mark.real_model

API = "/api/v1/documents"

TOPICS = [
    (
        "physics.pdf",
        "Quantum Mechanics",
        [
            (
                "Wave Functions",
                "Quantum mechanics describes nature at atomic scales. " * 15,
            ),
            (
                "Entanglement",
                "Quantum entanglement links particles across distances. " * 15,
            ),
        ],
    ),
    (
        "cooking.pdf",
        "Italian Cooking",
        [
            (
                "Pasta Dough",
                "Making fresh pasta requires flour eggs and patience. " * 15,
            ),
            ("Sauces", "A good tomato sauce simmers for hours with basil. " * 15),
        ],
    ),
    (
        "history.pdf",
        "Ancient Rome",
        [
            (
                "The Republic",
                "Rome began as a republic with senates and consuls. " * 15,
            ),
            ("The Empire", "Augustus became the first emperor of Rome. " * 15),
        ],
    ),
]


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    engine = create_engine(os.environ["DATABASE_URL"])
    factory = create_session_factory(engine)
    async with factory() as session:
        await session.execute(
            text("TRUNCATE documents, chunks, conversations, messages CASCADE")
        )
        await session.commit()
    await engine.dispose()


def upload(client: TestClient, pdfs: list[tuple[str, bytes]]):
    files = [("files", (name, data, "application/pdf")) for name, data in pdfs]
    return client.post(f"{API}/upload", files=files)


def wait_for(client: TestClient, doc_id: str, wanted: str, timeout: int = 900):
    deadline = time.time() + timeout
    body = {}
    while time.time() < deadline:
        body = client.get(f"{API}/{doc_id}").json()
        if body["status"] == wanted:
            return body
        time.sleep(3)
    raise TimeoutError(f"{doc_id} never reached {wanted}: {body}")


async def _verify_corpus(doc_ids: list[str], client: TestClient) -> None:
    """Check stored chunks, embeddings, citation metadata, and retrieval."""
    engine = create_engine(os.environ["DATABASE_URL"])
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            docs_repo = DocumentRepository(session)
            chunks_repo = ChunkRepository(session)

            for did in doc_ids:
                items, total = await chunks_repo.list_by_document(uuid.UUID(did))
                assert total > 0, f"no chunks stored for {did}"
                for c in items:
                    assert len(c.embedding) == 384, "embedding must be 384-dim"
                    assert c.page_numbers, "chunks need page numbers for citations"
                    assert c.token_count > 0
                    assert c.content.strip()

            # Semantic check with the REAL embedding model (shared app singleton).
            embedder = client.app.state.embedder
            query_vec = await asyncio.to_thread(
                embedder.embed, ["quantum mechanics wave functions"]
            )
            results = await chunks_repo.vector_search(query_vec[0], top_k=3)
            assert results, "vector search returned nothing"
            top_doc = await docs_repo.get(results[0].document_id)
            assert top_doc is not None
            assert top_doc.original_name == "physics.pdf", (
                f"expected physics.pdf on top, got "
                f"{[r.document_name for r in results]}"
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_e2e_ingest_three_pdfs_and_search(client: TestClient):
    from tests.factories import make_test_pdf

    pdfs = [
        make_test_pdf(title, sections, filename=name)
        for name, title, sections in TOPICS
    ]
    resp = upload(client, pdfs)
    assert resp.status_code == 202, resp.text
    doc_ids = [d["id"] for d in resp.json()["documents"]]
    assert len(doc_ids) == 3

    try:
        metas = [wait_for(client, did, "processed") for did in doc_ids]
        for meta in metas:
            assert meta["chunk_count"] > 0, meta
            assert meta["page_count"] == 2, meta  # title+section1, then section2
            assert meta["error_message"] is None
            assert meta["status"] == "processed"

        asyncio.run(_verify_corpus(doc_ids, client))
    finally:
        for did in doc_ids:  # cleanup: removes DB rows AND uploaded files
            client.delete(f"{API}/{did}")


@pytest.mark.integration
def test_e2e_corrupt_pdf_fails_cleanly_and_recovers(client: TestClient):
    resp = upload(
        client, [("broken.pdf", b"%PDF- this is not a real pdf \x00\x01\x02")]
    )
    assert resp.status_code == 202
    doc_id = resp.json()["documents"][0]["id"]

    failed = wait_for(client, doc_id, "failed", timeout=600)
    assert failed["error_message"], "failure must explain itself"
    assert failed["chunk_count"] == 0
    # No internal paths leak into the user-facing message.
    assert "/data" not in failed["error_message"]
    assert "/tmp" not in failed["error_message"]

    # Recoverable: the failed document can be deleted.
    assert client.delete(f"{API}/{doc_id}").status_code == 204
