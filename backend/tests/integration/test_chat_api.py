"""Integration tests for the chat/RAG API (POST /api/v1/chat/query).

The embedding model and the LLM are stubbed via dependency injection —
these tests verify retrieval wiring, context construction, citation mapping,
scoping, short-circuits, validation, and error mapping. Real Groq calls are
never made (no key in this environment); the Groq client itself is covered
by ``test_groq_client.py`` with a mocked HTTP transport.
"""

import json
import os
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.deps import get_rag_service
from app.config import get_settings
from app.db.models import Chunk, Document
from app.db.session import create_engine, create_session_factory
from app.services import (
    EmbeddingProvider,
    LLMProvider,
    LLMUpstreamError,
    RAGService,
)
from app.services.rag import NO_CONTEXT_MESSAGE, NO_DOCUMENTS_MESSAGE

API = "/api/v1/chat/query"
DIM = 384


def one_hot(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    return v


def tilted() -> list[float]:
    # cosine similarity 0.8 to one_hot(0)
    return [0.8, 0.6] + [0.0] * (DIM - 2)


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


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """SlowAPI's in-memory bucket survives across tests — reset per test."""
    from app.core.rate_limit import limiter

    limiter._storage.reset()
    yield
    limiter._storage.reset()


# ── Stubs ─────────────────────────────────────────────────────────────


class StubEmbedder(EmbeddingProvider):
    """Deterministic embedder: records inputs, returns a fixed vector."""

    def __init__(self, vector: list[float] | None = None) -> None:
        self._vector = vector or one_hot(0)
        self.queries: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.queries.extend(texts)
        return [list(self._vector) for _ in texts]


class StubLLM(LLMProvider):
    def __init__(self, answer: str = "stub answer", fail: bool = False) -> None:
        self.answer = answer
        self.fail = fail
        self.calls: list[dict] = []

    @property
    def model(self) -> str:
        return "stub-model"

    async def chat(self, *, system, user, max_tokens=1024, temperature=0.2):
        self.calls.append({"system": system, "user": user})
        if self.fail:
            raise LLMUpstreamError()
        return self.answer


@pytest.fixture
def rag_stubs(client: TestClient):
    embedder = StubEmbedder()
    llm = StubLLM()
    service = RAGService(
        settings=get_settings(),
        embedder=embedder,
        llm=llm,
        session_factory=client.app.state.session_factory,
    )
    client.app.dependency_overrides[get_rag_service] = lambda: service
    yield SimpleNamespace(embedder=embedder, llm=llm, service=service)
    client.app.dependency_overrides.clear()


def seed_documents(client: TestClient, docs: list[dict]) -> dict[str, uuid.UUID]:
    """Seed documents + chunks. Each doc: {name, status?, chunks?}.

    Each chunk: (content, vector, pages, heading).
    Returns {name: document_id}.

    Seeding runs on the TestClient's portal loop — the same loop that owns
    the app's async engine — avoiding event-loop mismatches.
    """

    async def _seed() -> dict[str, uuid.UUID]:
        factory = client.app.state.session_factory
        ids: dict[str, uuid.UUID] = {}
        async with factory() as session:
            for d in docs:
                doc = Document(
                    filename=f"{uuid.uuid4()}.pdf",
                    original_name=d["name"],
                    file_size=100,
                    status=d.get("status", "processed"),
                    page_count=1,
                    chunk_count=len(d.get("chunks", [])),
                )
                session.add(doc)
                await session.flush()
                for i, (content, vector, pages, heading) in enumerate(
                    d.get("chunks", [])
                ):
                    session.add(
                        Chunk(
                            document_id=doc.id,
                            chunk_index=i,
                            content=content,
                            page_numbers=pages,
                            heading_path=heading,
                            token_count=10,
                            embedding=vector,
                        )
                    )
                ids[d["name"]] = doc.id
            await session.commit()
        return ids

    return client.portal.call(_seed)


def query(client: TestClient, question: str = "What is the capital?", **kwargs):
    return client.post(API, json={"question": question, **kwargs})


# ── Retrieval + answer flow ───────────────────────────────────────────


async def test_query_full_flow_across_all_documents(client: TestClient, rag_stubs):
    ids = seed_documents(
        client,
        [
            {
                "name": "a.pdf",
                "chunks": [("Alpha content here.", one_hot(0), [1], "Intro")],
            },
            {
                "name": "b.pdf",
                "chunks": [("Beta content here.", tilted(), [2, 3], "Details")],
            },
        ],
    )
    rag_stubs.llm.answer = "Alpha says X [1], while Beta says Y [2]."

    resp = query(client, "What do the documents say?")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == "Alpha says X [1], while Beta says Y [2]."
    assert body["model"] == "stub-model"
    assert body["latency_ms"] >= 0

    # Embedding generation: the question reached the embedder.
    assert rag_stubs.embedder.queries == ["What do the documents say?"]

    # Retrieval spanned both documents (no accidental exclusion).
    # Citation order follows the answer: [1] → a.pdf chunk, [2] → b.pdf chunk.
    sources = body["sources"]
    assert len(sources) == 2
    assert sources[0]["filename"] == "a.pdf"
    assert sources[0]["document_id"] == str(ids["a.pdf"])
    assert sources[0]["pages"] == [1]
    assert sources[0]["heading"] == "Intro"
    assert sources[0]["similarity"] == 1.0
    assert "Alpha content" in sources[0]["snippet"]
    assert sources[1]["filename"] == "b.pdf"
    assert sources[1]["pages"] == [2, 3]
    assert sources[1]["similarity"] == pytest.approx(0.8)

    # Context construction: the LLM saw numbered blocks + the question.
    llm_input = rag_stubs.llm.calls[0]
    assert "What do the documents say?" in llm_input["user"]
    assert '[1] (Document: "a.pdf"' in llm_input["user"]
    assert '[2] (Document: "b.pdf"' in llm_input["user"]
    assert "ONLY" in llm_input["system"]


async def test_query_scoped_to_document_ids(client: TestClient, rag_stubs):
    ids = seed_documents(
        client,
        [
            {"name": "a.pdf", "chunks": [("Alpha.", one_hot(0), [1], "")]},
            {"name": "b.pdf", "chunks": [("Beta.", one_hot(0), [1], "")]},
        ],
    )
    rag_stubs.llm.answer = "Beta only [1]."

    resp = query(client, "scoped?", document_ids=[str(ids["b.pdf"])])

    assert resp.status_code == 200, resp.text
    sources = resp.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["filename"] == "b.pdf"


async def test_query_unknown_document_id_404(client: TestClient, rag_stubs):
    resp = query(client, "scoped?", document_ids=[str(uuid.uuid4())])
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


async def test_query_unprocessed_document_id_422(client: TestClient, rag_stubs):
    ids = seed_documents(client, [{"name": "p.pdf", "status": "pending"}])
    resp = query(client, "scoped?", document_ids=[str(ids["p.pdf"])])
    assert resp.status_code == 422
    assert resp.json()["code"] == "DOCUMENT_NOT_PROCESSED"


async def test_query_no_citations_gives_empty_sources(client: TestClient, rag_stubs):
    seed_documents(
        client,
        [{"name": "a.pdf", "chunks": [("Alpha.", one_hot(0), [1], "")]}],
    )
    rag_stubs.llm.answer = (
        "I don't have enough information in the uploaded documents to answer that."
    )

    resp = query(client, "Something obscure?")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sources"] == []
    assert "enough information" in body["answer"]


# ── Short-circuits (no LLM call) ─────────────────────────────────────


async def test_query_no_documents_short_circuits(client: TestClient, rag_stubs):
    resp = query(client, "Anything?")
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == NO_DOCUMENTS_MESSAGE
    assert body["sources"] == []
    assert rag_stubs.llm.calls == []
    assert rag_stubs.embedder.queries == []


async def test_query_no_chunks_retrieved_short_circuits(client: TestClient, rag_stubs):
    # A processed document with zero chunks: nothing to retrieve.
    seed_documents(client, [{"name": "empty.pdf", "chunks": []}])
    resp = query(client, "Anything?")
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == NO_CONTEXT_MESSAGE
    assert body["sources"] == []
    assert rag_stubs.llm.calls == []


# ── Validation ────────────────────────────────────────────────────────


async def test_query_validation(client: TestClient, rag_stubs):
    assert query(client, "ab").status_code == 422  # too short
    assert query(client, "x" * 2001).status_code == 422  # too long
    assert query(client, "ok?", top_k=0).status_code == 422
    assert query(client, "ok?", top_k=21).status_code == 422
    resp = query(client, "ok?", document_ids=["not-a-uuid"])
    assert resp.status_code == 422


# ── Error handling ────────────────────────────────────────────────────


async def test_query_llm_not_configured_503(client: TestClient):
    # No stub override: app.state.llm is None (no GROQ_API_KEY in tests).
    seed_documents(
        client,
        [{"name": "a.pdf", "chunks": [("Alpha.", one_hot(0), [1], "")]}],
    )
    resp = query(client, "Anything?")
    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "LLM_NOT_CONFIGURED"
    # Naming the env var is fine (it's public config documentation);
    # a key *value* must never appear.
    assert "GROQ_API_KEY" in body["message"]
    serialized = json.dumps(body)
    assert "gsk_" not in serialized
    assert "Bearer" not in serialized


async def test_query_llm_failure_maps_to_502(client: TestClient, rag_stubs):
    seed_documents(
        client,
        [{"name": "a.pdf", "chunks": [("Alpha.", one_hot(0), [1], "")]}],
    )
    rag_stubs.llm.fail = True
    resp = query(client, "Anything?")
    assert resp.status_code == 502
    assert resp.json()["code"] == "LLM_UPSTREAM_ERROR"


async def test_query_rate_limited(client: TestClient, rag_stubs):
    # 20/minute: the 21st request is rejected. Runs on the empty corpus,
    # so each request short-circuits fast.
    last = None
    for _ in range(21):
        last = query(client, "Anything?")
    assert last is not None
    assert last.status_code == 429
    assert last.json()["code"] == "RATE_LIMITED"
