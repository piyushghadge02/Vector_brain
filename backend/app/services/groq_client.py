"""LLM provider abstraction + Groq implementation.

The ``LLMProvider`` ABC keeps the RAG service testable without an API key:
tests inject a stub. The Groq implementation talks to Groq's OpenAI-compatible
endpoint with retries on transient failures.

The API key is only ever sent as an Authorization header — it is never
logged, never returned, and never included in error messages.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import anyio
import httpx

from app.core.errors import AppError

logger = logging.getLogger("vectorbrain.groq")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMProvider(ABC):
    """Generates a completion from a system + user prompt pair."""

    @abstractmethod
    async def chat(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        """Return the assistant's reply text."""
        raise NotImplementedError


class LLMNotConfiguredError(AppError):
    code = "LLM_NOT_CONFIGURED"
    message = (
        "The chat service is not configured: GROQ_API_KEY is missing. "
        "Set it in the backend environment to enable question answering."
    )
    status_code = 503


class LLMUpstreamError(AppError):
    code = "LLM_UPSTREAM_ERROR"
    message = "The language model service failed to respond. Please try again."
    status_code = 502


class GroqLLMProvider(LLMProvider):
    """Groq chat completions via the OpenAI-compatible API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = GROQ_BASE_URL,
        timeout_seconds: float = 60.0,
        max_retries: int = 1,
        transport: httpx.AsyncHTTPTransport | None = None,
    ) -> None:
        if not api_key:
            raise LLMNotConfiguredError()
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._transport = transport  # injected in tests (httpx.MockTransport)

    @property
    def model(self) -> str:
        return self._model

    async def chat(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        # Never log headers or payload: the key must not end up in logs.
        headers = {"Authorization": f"Bearer {self._api_key}"}

        last_error: Exception | None = None
        async with httpx.AsyncClient(
            transport=self._transport, timeout=self._timeout
        ) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    resp = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                except httpx.TimeoutException as exc:
                    last_error = exc
                    logger.warning("groq request timed out (attempt %d)", attempt + 1)
                except httpx.HTTPError as exc:
                    # Network-level failure: not retryable blindly, surface it.
                    logger.warning("groq request failed: %s", type(exc).__name__)
                    raise LLMUpstreamError() from exc
                else:
                    if resp.status_code == 200:
                        return self._extract_content(resp)
                    if (
                        resp.status_code in RETRYABLE_STATUS
                        and attempt < self._max_retries
                    ):
                        logger.warning(
                            "groq returned %d, retrying (attempt %d)",
                            resp.status_code,
                            attempt + 1,
                        )
                        await anyio.sleep(2**attempt)
                        continue
                    logger.warning("groq returned %d", resp.status_code)
                    raise LLMUpstreamError()
                if attempt < self._max_retries:
                    await anyio.sleep(2**attempt)

        logger.error("groq request failed after retries: %s", type(last_error).__name__)
        raise LLMUpstreamError() from last_error

    @staticmethod
    def _extract_content(resp: httpx.Response) -> str:
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("groq returned an unexpected payload shape")
            raise LLMUpstreamError() from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMUpstreamError()
        return content.strip()
