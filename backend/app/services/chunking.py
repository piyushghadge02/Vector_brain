"""Chunking: split a DoclingDocument into searchable text chunks.

Primary strategy is Docling's ``HybridChunker`` (structure-aware: it keeps
headings attached and merges small peer sections). Each chunk carries the
citation metadata the frontend needs: page numbers and heading breadcrumb.

Heavy imports (``transformers``) are lazy so importing this module is cheap.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger("vectorbrain.chunking")


def _log_timing(label: str, start: float, extra: str = "") -> float:
    """Log elapsed time since start and return new timestamp."""
    elapsed = time.perf_counter() - start
    logger.info("timing: %s took %.3fs %s", label, elapsed, extra)
    return time.perf_counter()


@dataclass(frozen=True)
class TextChunk:
    """One searchable unit of a document."""

    text: str
    page_numbers: list[int]
    heading_path: str  # breadcrumb, e.g. "Chapter 2 > 2.1 Background"
    token_count: int


class Chunker(ABC):
    """Splits a converted document into :class:`TextChunk` items."""

    @abstractmethod
    def chunk(self, document) -> list[TextChunk]:
        """Chunk a DoclingDocument. Raises on empty/unusable input."""
        raise NotImplementedError


class DoclingHybridChunker(Chunker):
    """Docling ``HybridChunker`` backed by the MiniLM tokenizer.

    ``max_tokens`` bounds chunk size for the embedding model; ``merge_peers``
    joins undersized sibling sections so chunks stay semantically coherent.
    """

    def __init__(
        self,
        tokenizer_id: str = "sentence-transformers/all-MiniLM-L6-v2",
        max_tokens: int = 512,
    ) -> None:
        self._tokenizer_id = tokenizer_id
        self._max_tokens = max_tokens
        self._chunker = None
        self._tokenizer = None
        self._lock = threading.Lock()

    def _get_chunker(self):
        if self._chunker is None:
            with self._lock:
                if self._chunker is None:
                    from docling.chunking import HybridChunker
                    from docling_core.transforms.chunker.tokenizer.huggingface import (
                        HuggingFaceTokenizer,
                    )
                    from transformers import AutoTokenizer

                    t0 = time.perf_counter()
                    logger.info("loading tokenizer %s", self._tokenizer_id)
                    hf_tokenizer = AutoTokenizer.from_pretrained(self._tokenizer_id)
                    t0 = _log_timing("tokenizer_load", t0)
                    self._tokenizer = HuggingFaceTokenizer(
                        tokenizer=hf_tokenizer, max_tokens=self._max_tokens
                    )
                    self._chunker = HybridChunker(
                        tokenizer=self._tokenizer, merge_peers=True
                    )
                    _log_timing("chunker_init", t0)
        return self._chunker

    def chunk(self, document) -> list[TextChunk]:
        t0 = time.perf_counter()
        chunker = self._get_chunker()
        t0 = _log_timing("chunker_get", t0)
        chunks: list[TextChunk] = []
        for raw in chunker.chunk(dl_doc=document):
            text = (raw.text or "").strip()
            if not text:
                continue
            meta = raw.meta
            pages = sorted(
                {
                    prov.page_no
                    for item in (meta.doc_items or [])
                    for prov in (item.prov or [])
                    if getattr(prov, "page_no", None)
                }
            )
            headings = meta.headings or []
            chunks.append(
                TextChunk(
                    text=text,
                    page_numbers=pages,
                    heading_path=" > ".join(headings),
                    token_count=self._tokenizer.count_tokens(text),
                )
            )
        _log_timing("chunking_total", t0, f"chunks={len(chunks)}")
        return chunks
