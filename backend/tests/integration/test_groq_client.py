"""Tests for the Groq LLM client against a mocked HTTP transport.

No real API key or network access is used — httpx.MockTransport simulates
Groq's OpenAI-compatible responses.
"""

import json

import httpx
import pytest

from app.services.groq_client import (
    GroqLLMProvider,
    LLMNotConfiguredError,
    LLMUpstreamError,
)

SUCCESS = {"choices": [{"message": {"content": "  hello world  "}}]}


def make_client(handler, **kwargs) -> GroqLLMProvider:
    transport = httpx.MockTransport(handler)
    return GroqLLMProvider(
        api_key="gsk_test_key", model="test-model", transport=transport, **kwargs
    )


async def test_chat_success_sends_auth_and_strips_content():
    def handler(request: httpx.Request) -> httpx.Response:
        # Key travels as a Bearer header and is never in the URL/body.
        assert request.headers["Authorization"] == "Bearer gsk_test_key"
        assert "gsk_test_key" not in str(request.url)
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        assert body["temperature"] == 0.2
        return httpx.Response(200, json=SUCCESS)

    client = make_client(handler)
    assert await client.chat(system="sys", user="usr") == "hello world"


async def test_chat_retries_once_on_429_then_succeeds():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return httpx.Response(200, json=SUCCESS)

    client = make_client(handler, max_retries=1)
    assert await client.chat(system="s", user="u") == "hello world"
    assert len(calls) == 2


async def test_chat_raises_upstream_error_after_retries_exhausted():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500, json={"error": "boom"})

    client = make_client(handler, max_retries=1)
    with pytest.raises(LLMUpstreamError):
        await client.chat(system="s", user="u")
    assert len(calls) == 2  # initial + one retry


async def test_chat_raises_on_non_retryable_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(LLMUpstreamError):
        await make_client(handler, max_retries=0).chat(system="s", user="u")


async def test_chat_retries_then_raises_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow")

    with pytest.raises(LLMUpstreamError):
        await make_client(handler, max_retries=1).chat(system="s", user="u")


async def test_chat_raises_on_unexpected_payload_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    with pytest.raises(LLMUpstreamError):
        await make_client(handler).chat(system="s", user="u")


def test_missing_api_key_fails_fast_at_construction():
    with pytest.raises(LLMNotConfiguredError):
        GroqLLMProvider(api_key="", model="test-model")
