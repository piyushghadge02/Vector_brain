"""Embedding providers — 384-dimensional, L2-normalized vectors.

The ``EmbeddingProvider`` ABC keeps the ingestion pipeline testable without
downloading the ~90 MB model: tests inject a deterministic stub.

Heavy imports (``sentence_transformers`` → torch) are lazy so that merely
importing this module never pays the import cost or requires the model.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod

logger = logging.getLogger("vectorbrain.embeddings")


def _log_timing(label: str, start: float, extra: str = "") -> float:
    """Log elapsed time since start and return new timestamp."""
    elapsed = time.perf_counter() - start
    logger.info("timing: %s took %.3fs %s", label, elapsed, extra)
    return time.perf_counter()


class EmbeddingProvider(ABC):
    """Generates one embedding per input text."""

    dim: int = 384

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return a ``(len(texts), dim)`` list of L2-normalized vectors."""
        raise NotImplementedError


class MiniLMEmbeddingProvider(EmbeddingProvider):
    """``sentence-transformers/all-MiniLM-L6-v2`` — 384 dims, CPU-friendly.

    The model (~90 MB) downloads from Hugging Face on first use and is then
    cached. Thread-safe: a lock guards both lazy init and ``encode``.
    """

    def __init__(
        self,
        model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
    ) -> None:
        self._model_id = model_id
        self._batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    t0 = time.perf_counter()
                    logger.info("loading embedding model %s", self._model_id)
                    self._model = SentenceTransformer(self._model_id)
                    _log_timing("embedding_model_load", t0)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        t0 = time.perf_counter()
        model = self._get_model()
        t0 = _log_timing("embedding_model_get", t0)
        with self._lock:
            vectors = model.encode(
                texts,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        t0 = _log_timing("embedding_encode", t0, f"texts={len(texts)}")
        result = [list(map(float, row)) for row in vectors]
        assert all(len(row) == self.dim for row in result), "dimension mismatch"
        _log_timing("embedding_total", t0, f"vectors={len(result)}")
        return result
