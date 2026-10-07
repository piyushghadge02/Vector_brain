"""Unit tests for RAG helpers: context building, prompts, citations."""

import uuid

from app.repositories.chunks import ChunkSearchResult
from app.services.rag import (
    INSUFFICIENT_CONTEXT_SENTINEL,
    SYSTEM_PROMPT,
    build_context,
    build_user_prompt,
    extract_citations,
    format_pages,
)


def make_hit(
    idx: int, name: str = "doc.pdf", pages: list[int] | None = None
) -> ChunkSearchResult:
    return ChunkSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name=name,
        content=f"content of chunk {idx} " * 10,
        page_numbers=pages or [idx + 1],
        heading_path="Chapter 1",
        similarity=0.9 - idx * 0.1,
    )


def test_format_pages():
    assert format_pages([]) == "page ?"
    assert format_pages([2]) == "page 2"
    assert format_pages([1, 2, 3]) == "pages 1–3"


def test_build_context_numbers_and_labels():
    hits = [make_hit(0, "a.pdf", [2]), make_hit(1, "b.pdf", [5, 6])]
    ctx = build_context(hits, max_chars=10_000)
    assert '[1] (Document: "a.pdf", page 2)' in ctx
    assert '[2] (Document: "b.pdf", pages 5–6)' in ctx
    assert "content of chunk 0" in ctx
    assert "content of chunk 1" in ctx


def test_build_context_respects_budget_but_keeps_first():
    hits = [make_hit(0), make_hit(1), make_hit(2)]
    # Tiny budget: first block always survives, the rest are cut.
    ctx = build_context(hits, max_chars=50)
    assert "[1]" in ctx
    assert "[2]" not in ctx


def test_build_user_prompt_contains_question_and_context():
    prompt = build_user_prompt("What is X?", "[1] some context")
    assert "What is X?" in prompt
    assert "[1] some context" in prompt


def test_system_prompt_demands_grounding_and_honesty():
    assert "[1]" in SYSTEM_PROMPT or "square brackets" in SYSTEM_PROMPT
    assert INSUFFICIENT_CONTEXT_SENTINEL in SYSTEM_PROMPT
    assert "ONLY" in SYSTEM_PROMPT


def test_extract_citations_orders_dedupes_and_drops_invalid():
    hits = [make_hit(0), make_hit(1), make_hit(2)]
    cited = extract_citations("As shown in [2] and [1], and again [2]; see [99].", hits)
    assert [c.content for c in cited] == [hits[1].content, hits[0].content]


def test_extract_citations_empty_when_none():
    hits = [make_hit(0)]
    assert extract_citations("No citations here.", hits) == []
    assert extract_citations(INSUFFICIENT_CONTEXT_SENTINEL, hits) == []


def test_extract_citations_accepts_cjk_brackets():
    # gpt-oss renders citations as 【n】 instead of [n] — still map them.
    hits = [make_hit(0), make_hit(1)]
    cited = extract_citations("As shown in 【2】 and 【1】.", hits)
    assert [c.content for c in cited] == [hits[1].content, hits[0].content]
