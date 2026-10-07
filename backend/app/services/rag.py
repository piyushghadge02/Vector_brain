"""RAG orchestration: question → retrieval → grounded answer + citations.

Pipeline:
    1. Validate the question.
    2. Fail fast if the LLM is not configured.
    3. Embed the question with the same 384-dim model used at ingestion.
    4. pgvector cosine search over **all processed documents** by default;
       an explicit ``document_ids`` list scopes the search (validated).
    5. Short-circuit with a helpful message when nothing is retrieved —
       no point spending an LLM call.
    6. Build a token-budgeted context, prompt the LLM with grounding rules,
       and map ``[n]`` citations back to source metadata.

The service never touches HTTP; the API layer calls :meth:`ask`.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field

import anyio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.errors import NotFoundError, ValidationError
from app.repositories import ChunkRepository, ChunkSearchResult, DocumentRepository
from app.services.embeddings import EmbeddingProvider
from app.services.groq_client import LLMNotConfiguredError, LLMProvider

logger = logging.getLogger("vectorbrain.rag")

# Models don't always obey the [n] convention — gpt-oss, for example,
# renders citations as 【n】 (CJK brackets). Accept both so a cited answer
# never comes back with empty sources.
CITATION_RE = re.compile(r"\[(\d+)\]|【(\d+)】")

NO_DOCUMENTS_MESSAGE = (
    "I don't have any processed documents to search yet. "
    "Upload some PDFs first, then ask me anything about them."
)
NO_CONTEXT_MESSAGE = (
    "I couldn't find anything relevant in the uploaded documents. "
    "Try rephrasing your question or upload documents covering this topic."
)
INSUFFICIENT_CONTEXT_SENTINEL = (
    "I don't have enough information in the uploaded documents to answer that."
)

SYSTEM_PROMPT = """You are VectorBrain, a research assistant that answers questions \
using ONLY the context provided from the user's uploaded documents.

Rules:
1. Base your answer strictly on the context below. Do not use outside knowledge.
2. Cite every factual claim with its source number in plain ASCII square
   brackets, e.g. [1], [2] — never any other bracket style.
3. If the context does not contain enough information to answer, say exactly: \
"I don't have enough information in the uploaded documents to answer that." \
Do not invent details.
4. Be concise but complete."""


def format_pages(pages: list[int]) -> str:
    if not pages:
        return "page ?"
    if len(pages) == 1:
        return f"page {pages[0]}"
    return f"pages {pages[0]}–{pages[-1]}"


def build_context(results: list[ChunkSearchResult], max_chars: int) -> str:
    """Assemble numbered context blocks, truncated to a character budget."""
    blocks: list[str] = []
    used = 0
    for i, r in enumerate(results, start=1):
        header = (
            f'[{i}] (Document: "{r.document_name}", {format_pages(r.page_numbers)})\n'
        )
        body = r.content.strip()
        # Reserve room for the header and a separator; stop before overflow.
        if used + len(header) + len(body) + 2 > max_chars and blocks:
            break
        blocks.append(header + body)
        used += len(header) + len(body) + 2
    return "\n\n".join(blocks)


def build_user_prompt(question: str, context: str) -> str:
    return (
        "Answer the question using ONLY the context below, citing sources.\n\n"
        f"Context from uploaded documents:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer (with [n] citations):"
    )


def extract_citations(
    answer: str, results: list[ChunkSearchResult]
) -> list[ChunkSearchResult]:
    """Map ``[n]`` citations in the answer back to retrieved chunks.

    Order follows first appearance in the answer; duplicates collapse;
    out-of-range references are dropped defensively.
    """
    order: list[int] = []
    for match in CITATION_RE.finditer(answer):
        num = match.group(1) or match.group(2)  # [n] or 【n】
        idx = int(num) - 1
        if 0 <= idx < len(results) and idx not in order:
            order.append(idx)
    return [results[i] for i in order]


@dataclass(frozen=True)
class CitedSource:
    document_id: uuid.UUID
    filename: str
    chunk_id: uuid.UUID
    pages: list[int]
    heading: str
    snippet: str
    similarity: float


@dataclass(frozen=True)
class QueryResult:
    answer: str
    sources: list[CitedSource]
    model: str
    latency_ms: int
    chunks_retrieved: int = field(default=0)


class RAGService:
    """Answers questions over the ingested corpus."""

    def __init__(
        self,
        *,
        settings,
        embedder: EmbeddingProvider,
        llm: LLMProvider | None,
        session_factory: async_sessionmaker,
    ) -> None:
        self._settings = settings
        self._embedder = embedder
        self._llm = llm
        self._session_factory = session_factory

    async def ask(
        self,
        question: str,
        *,
        document_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
    ) -> QueryResult:
        started = time.perf_counter()
        q = self._validate_question(question)
        if self._llm is None:
            raise LLMNotConfiguredError()
        top_k = top_k or self._settings.retrieval_top_k

        async with self._session_factory() as session:
            docs_repo = DocumentRepository(session)
            chunks_repo = ChunkRepository(session)

            # Explicit scoping is validated first: a typo'd id must 404
            # loudly instead of silently excluding documents — even when
            # the corpus is empty.
            if document_ids:
                for did in document_ids:
                    doc = await docs_repo.get(did)
                    if doc is None:
                        raise NotFoundError(f"Document {did} not found.")
                    if doc.status != "processed":
                        raise ValidationError(
                            f"Document {did} is not processed yet "
                            f"(status: {doc.status}).",
                            code="DOCUMENT_NOT_PROCESSED",
                        )
            elif await docs_repo.count(status="processed") == 0:
                return self._result(NO_DOCUMENTS_MESSAGE, [], 0, started)

            # document_ids=None searches the WHOLE corpus — nothing is
            # excluded unless the caller explicitly scopes the query.
            query_vector = await anyio.to_thread.run_sync(self._embedder.embed, [q])
            results = await chunks_repo.vector_search(
                query_vector[0], top_k=top_k, document_ids=document_ids
            )
            if not results:
                return self._result(NO_CONTEXT_MESSAGE, [], 0, started)

            context = build_context(
                results, max_chars=self._settings.rag_max_context_tokens * 4
            )
            answer = await self._llm.chat(
                system=SYSTEM_PROMPT,
                user=build_user_prompt(q, context),
                max_tokens=self._settings.llm_max_tokens,
                temperature=self._settings.llm_temperature,
            )
            sources = [
                CitedSource(
                    document_id=r.document_id,
                    filename=r.document_name,
                    chunk_id=r.chunk_id,
                    pages=list(r.page_numbers),
                    heading=r.heading_path,
                    snippet=r.content[:200].strip(),
                    similarity=round(r.similarity, 4),
                )
                for r in extract_citations(answer, results)
            ]
            logger.info(
                "answered question (%d chars): %d chunks retrieved, %d cited",
                len(q),
                len(results),
                len(sources),
            )
            return self._result(answer, sources, len(results), started)

    def _validate_question(self, question: str) -> str:
        q = (question or "").strip()
        if len(q) < 3:
            raise ValidationError(
                "Question must be at least 3 characters.", code="QUESTION_TOO_SHORT"
            )
        if len(q) > 2000:
            raise ValidationError(
                "Question must be at most 2000 characters.", code="QUESTION_TOO_LONG"
            )
        return q

    def _result(
        self,
        answer: str,
        sources: list[CitedSource],
        chunks_retrieved: int,
        started: float,
    ) -> QueryResult:
        model = self._llm.model if self._llm is not None else "unconfigured"
        return QueryResult(
            answer=answer,
            sources=sources,
            model=model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            chunks_retrieved=chunks_retrieved,
        )
