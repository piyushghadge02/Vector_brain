"""Integration tests for the repository layer.

Requires a real PostgreSQL + pgvector database with migrations applied::

    DATABASE_URL=postgresql+asyncpg://vectorbrain:vectorbrain@localhost:5432/vectorbrain_test \\
        pytest tests/integration/test_repositories.py

Each test runs against a freshly truncated schema (see the ``session``
fixture), so tests are isolated and order-independent. Vectors are
deterministic one-hot unit vectors — no ML model is downloaded.
"""

import math
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import create_engine, create_session_factory
from app.repositories import ChunkCreate, ChunkRepository, DocumentRepository

DIM = 384


def one_hot(i: int) -> list[float]:
    """Deterministic 384-dim L2-normalized vector with a 1 at position i."""
    v = [0.0] * DIM
    v[i] = 1.0
    return v


@pytest_asyncio.fixture
async def session():
    # Engine is created inside the test's event loop (never at import time).
    engine = create_engine(os.environ["DATABASE_URL"])
    factory = create_session_factory(engine)
    async with factory() as s:
        await s.execute(
            text("TRUNCATE documents, chunks, conversations, messages CASCADE")
        )
        await s.commit()
        yield s
        await s.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def docs(session: AsyncSession) -> DocumentRepository:
    return DocumentRepository(session)


@pytest_asyncio.fixture
async def chunks(session: AsyncSession) -> ChunkRepository:
    return ChunkRepository(session)


async def make_doc(
    session: AsyncSession,
    docs: DocumentRepository,
    chunks: ChunkRepository,
    name: str,
    vectors: list[list[float]],
    status: str = "processed",
):
    doc = await docs.create(
        filename=f"{name}.pdf", original_name=f"{name}.pdf", file_size=1234
    )
    await docs.update_status(doc.id, status, page_count=2, chunk_count=len(vectors))
    await chunks.bulk_create(
        [
            ChunkCreate(
                document_id=doc.id,
                chunk_index=i,
                content=f"chunk {i} of {name}",
                token_count=10,
                embedding=v,
                page_numbers=[i + 1],
                heading_path=f"{name} > section",
            )
            for i, v in enumerate(vectors)
        ]
    )
    await session.commit()
    return doc


# ── Connection ────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_connection_and_pgvector_extension(session: AsyncSession):
    assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
    row = (
        await session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
    ).first()
    assert row is not None, "pgvector extension is not installed"


# ── Documents ─────────────────────────────────────────────────────────


@pytest.mark.integration
async def test_create_and_get_document(docs: DocumentRepository):
    doc = await docs.create(
        filename="abc123.pdf",
        original_name="paper.pdf",
        file_size=1024,
        doc_metadata={"title": "A Paper"},
    )
    assert doc.id is not None
    assert doc.status == "pending"  # default lifecycle state
    assert doc.chunk_count == 0

    fetched = await docs.get(doc.id)
    assert fetched is not None
    assert fetched.original_name == "paper.pdf"
    assert fetched.doc_metadata == {"title": "A Paper"}
    assert fetched.created_at is not None

    assert await docs.get(uuid.uuid4()) is None


@pytest.mark.integration
async def test_list_documents_pagination_and_status_filter(
    session: AsyncSession, docs: DocumentRepository, chunks: ChunkRepository
):
    for i in range(5):
        await make_doc(
            session,
            docs,
            chunks,
            f"doc{i}",
            [one_hot(i)],
            status="processed" if i < 2 else "pending",
        )

    items, total = await docs.list(status="processed")
    assert total == 2
    assert {d.original_name for d in items} == {"doc0.pdf", "doc1.pdf"}

    items, total = await docs.list(page=1, size=2)
    assert total == 5 and len(items) == 2
    items, _ = await docs.list(page=3, size=2)
    assert len(items) == 1  # last page is partial

    with pytest.raises(ValueError):
        await docs.list(page=0)
    with pytest.raises(ValueError):
        await docs.list(status="bogus")


@pytest.mark.integration
async def test_update_document_status(docs: DocumentRepository):
    doc = await docs.create(filename="x.pdf", original_name="x.pdf", file_size=1)

    updated = await docs.update_status(doc.id, "processing", error_message=None)
    assert updated is not None and updated.status == "processing"

    updated = await docs.update_status(
        doc.id, "failed", error_message="could not parse"
    )
    assert updated.error_message == "could not parse"

    with pytest.raises(ValueError):
        await docs.update_status(doc.id, "bogus")
    assert await docs.update_status(uuid.uuid4(), "processed") is None


@pytest.mark.integration
async def test_delete_document_cascades_chunks(
    session: AsyncSession, docs: DocumentRepository, chunks: ChunkRepository
):
    doc = await make_doc(session, docs, chunks, "doomed", [one_hot(0), one_hot(1)])
    assert await chunks.count_by_document(doc.id) == 2

    assert await docs.delete(doc.id) is True
    assert await docs.get(doc.id) is None
    assert await chunks.count_by_document(doc.id) == 0  # cascaded
    assert await docs.delete(doc.id) is False  # idempotent


# ── Chunks & embeddings ───────────────────────────────────────────────


@pytest.mark.integration
async def test_chunk_embedding_roundtrip(
    session: AsyncSession, docs: DocumentRepository, chunks: ChunkRepository
):
    doc = await make_doc(session, docs, chunks, "rt", [one_hot(7)])
    items, total = await chunks.list_by_document(doc.id)
    assert total == 1
    stored = items[0]
    assert stored.chunk_index == 0
    assert stored.page_numbers == [1]
    assert stored.heading_path == "rt > section"
    assert len(stored.embedding) == DIM
    # pgvector stores float32 — compare approximately.
    assert stored.embedding == pytest.approx(one_hot(7), abs=1e-6)


@pytest.mark.integration
async def test_chunk_rejects_wrong_dimension(
    session: AsyncSession, docs: DocumentRepository, chunks: ChunkRepository
):
    doc = await docs.create(filename="x.pdf", original_name="x.pdf", file_size=1)
    # pgvector's client-side binder rejects the wrong dimension before SQL
    # is even sent — a StatementError wrapping "expected 384 dimensions".
    with pytest.raises(StatementError, match="384"):
        await chunks.bulk_create(
            [
                ChunkCreate(
                    document_id=doc.id,
                    chunk_index=0,
                    content="bad",
                    token_count=1,
                    embedding=[1.0, 2.0, 3.0],  # 3 dims, not 384
                )
            ]
        )
    await session.rollback()


@pytest.mark.integration
async def test_chunk_pagination_count_and_delete(
    session: AsyncSession, docs: DocumentRepository, chunks: ChunkRepository
):
    doc = await make_doc(session, docs, chunks, "multi", [one_hot(i) for i in range(5)])
    assert await chunks.count_by_document(doc.id) == 5

    page1, total = await chunks.list_by_document(doc.id, page=1, size=2)
    assert total == 5 and [c.chunk_index for c in page1] == [0, 1]
    page3, _ = await chunks.list_by_document(doc.id, page=3, size=2)
    assert [c.chunk_index for c in page3] == [4]  # order preserved

    assert await chunks.delete_by_document(doc.id) == 5
    assert await chunks.count_by_document(doc.id) == 0


# ── Vector similarity search ──────────────────────────────────────────


@pytest.mark.integration
async def test_vector_search_orders_by_cosine_similarity(
    session: AsyncSession, docs: DocumentRepository, chunks: ChunkRepository
):
    doc_a = await make_doc(session, docs, chunks, "a", [one_hot(0), one_hot(1)])
    diag = [1 / math.sqrt(2), 1 / math.sqrt(2)] + [0.0] * (DIM - 2)
    doc_b = await make_doc(session, docs, chunks, "b", [diag])

    results = await chunks.vector_search(one_hot(0), top_k=10)

    assert [r.content for r in results] == [
        "chunk 0 of a",  # identical → similarity 1.0
        "chunk 0 of b",  # 45° away → similarity ≈ 0.7071
        "chunk 1 of a",  # orthogonal → similarity 0.0
    ]
    assert results[0].similarity == pytest.approx(1.0)
    assert results[1].similarity == pytest.approx(1 / math.sqrt(2))
    assert results[2].similarity == pytest.approx(0.0)
    assert results[0].document_id == doc_a.id
    assert results[1].document_id == doc_b.id
    assert results[0].document_name == "a.pdf"


@pytest.mark.integration
async def test_vector_search_scopes_to_document_ids(
    session: AsyncSession, docs: DocumentRepository, chunks: ChunkRepository
):
    await make_doc(session, docs, chunks, "a", [one_hot(0)])
    doc_b = await make_doc(session, docs, chunks, "b", [one_hot(0)])

    results = await chunks.vector_search(one_hot(0), document_ids=[doc_b.id])
    assert len(results) == 1
    assert results[0].document_id == doc_b.id


@pytest.mark.integration
async def test_vector_search_ignores_unprocessed_documents(
    session: AsyncSession, docs: DocumentRepository, chunks: ChunkRepository
):
    await make_doc(session, docs, chunks, "pending-doc", [one_hot(0)], status="pending")
    await make_doc(session, docs, chunks, "failed-doc", [one_hot(0)], status="failed")
    assert await chunks.vector_search(one_hot(0)) == []


@pytest.mark.integration
async def test_vector_search_top_k_and_min_similarity(
    session: AsyncSession, docs: DocumentRepository, chunks: ChunkRepository
):
    await make_doc(session, docs, chunks, "a", [one_hot(0), one_hot(1), one_hot(2)])

    assert len(await chunks.vector_search(one_hot(0), top_k=1)) == 1
    # Only the identical vector clears a 0.9 threshold.
    results = await chunks.vector_search(one_hot(0), min_similarity=0.9)
    assert len(results) == 1
    assert results[0].similarity == pytest.approx(1.0)

    with pytest.raises(ValueError):
        await chunks.vector_search(one_hot(0), top_k=0)
    with pytest.raises(ValueError):
        await chunks.vector_search([1.0, 2.0])  # wrong dimension
