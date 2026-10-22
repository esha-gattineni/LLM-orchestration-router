import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest

from app.config import settings
from app.models.schemas import ModelChoice, UsageStats
from app.services.llm_client import LLMClient, ProviderFailure, normalize_text


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    return LLMClient()


async def test_normalized_usage_and_content(client, monkeypatch):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        return_value=SimpleNamespace(
            content=[{"type": "text", "text": "Hello"}],
            usage_metadata={"input_tokens": 100, "output_tokens": 50},
            response_metadata={},
        )
    )
    monkeypatch.setattr(client, "_get_llm", lambda model: llm)
    text, usage = await client.complete([{"role": "user", "content": "Hi"}], ModelChoice.GPT4)
    assert text == "Hello"
    assert usage.total_tokens == 150
    assert usage.cost_usd == 0.00125


async def test_missing_usage_is_unknown(client, monkeypatch):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content="Hi", response_metadata={}))
    monkeypatch.setattr(client, "_get_llm", lambda model: llm)
    _, usage = await client.complete([{"role": "user", "content": "Hi"}], ModelChoice.GPT4)
    assert usage.cost_usd is None and usage.total_tokens is None
    assert not usage.usage_available


async def test_timeout_falls_back_with_total_latency(client, monkeypatch):
    calls = []

    async def complete(messages, model, max_tokens):
        calls.append(model)
        if model == ModelChoice.GPT4:
            await asyncio.sleep(1)
        return "ok", UsageStats(latency_ms=0)

    monkeypatch.setattr(client, "complete", complete)
    _, usage, model = await client.complete_with_fallback(
        [], ModelChoice.GPT4, latency_budget_ms=100
    )
    assert calls == [ModelChoice.GPT4, ModelChoice.CLAUDE]
    assert model == ModelChoice.CLAUDE
    assert 50 <= usage.latency_ms < 500


async def test_both_slow_cancel_at_deadline(client, monkeypatch):
    cancelled = []

    async def complete(messages, model, max_tokens):
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.append(model)

    monkeypatch.setattr(client, "complete", complete)
    with pytest.raises(TimeoutError):
        await client.complete_with_fallback([], ModelChoice.GPT4, latency_budget_ms=100)
    assert cancelled == [ModelChoice.GPT4, ModelChoice.CLAUDE]


async def test_programming_error_does_not_fallback(client, monkeypatch):
    fake = AsyncMock(side_effect=ValueError("bug"))
    monkeypatch.setattr(client, "complete", fake)
    with pytest.raises(ValueError):
        await client.complete_with_fallback([], ModelChoice.GPT4)
    assert fake.call_count == 1


async def test_rate_limit_fallback(client, monkeypatch):
    response = httpx.Response(429, request=httpx.Request("POST", "https://example.test"))
    fake = AsyncMock(
        side_effect=[
            openai.RateLimitError("rate limit", response=response, body=None),
            ("ok", UsageStats(latency_ms=0)),
        ]
    )
    monkeypatch.setattr(client, "complete", fake)
    assert (await client.complete_with_fallback([], ModelChoice.GPT4))[2] == ModelChoice.CLAUDE


async def test_auth_error_does_not_fallback(client, monkeypatch):
    response = httpx.Response(401, request=httpx.Request("POST", "https://example.test"))
    fake = AsyncMock(
        side_effect=openai.AuthenticationError("bad key", response=response, body=None)
    )
    monkeypatch.setattr(client, "complete", fake)
    with pytest.raises(ProviderFailure):
        await client.complete_with_fallback([], ModelChoice.GPT4)
    assert fake.call_count == 1


def test_lazy_construction_with_one_provider(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    client = LLMClient()
    assert client.available_models() == {ModelChoice.CLAUDE}
    assert client._get_llm(ModelChoice.CLAUDE) is not None
    assert ModelChoice.GPT4 not in client._clients


def test_openai_constructor(client, monkeypatch):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)
    assert client._get_llm(ModelChoice.GPT4) is not None


def test_unsupported_content():
    with pytest.raises(ProviderFailure):
        normalize_text([{"type": "tool_use"}])
