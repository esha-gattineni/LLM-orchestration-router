from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import ModelChoice, UsageStats
from app.routers import chat
from app.services.llm_client import ProviderFailure


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def provider(monkeypatch):
    fake = MagicMock()
    fake.available_models.return_value = {ModelChoice.GPT4, ModelChoice.CLAUDE}
    fake.complete_with_fallback = AsyncMock(
        return_value=(
            "hello",
            UsageStats(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                cost_usd=0.00033,
                latency_ms=2,
                usage_available=True,
            ),
            ModelChoice.CLAUDE,
        )
    )
    monkeypatch.setattr(chat, "get_llm_client", lambda: fake)
    return fake


def test_health_and_unconfigured_readiness(client):
    assert client.get("/health/").status_code == 200
    assert client.get("/health/ready").status_code == 503


def test_request_id_and_metrics(client, provider):
    response = client.post(
        "/api/v1/chat/completions", json={"messages": [{"role": "user", "content": "Hi"}]}
    )
    assert response.status_code == 200
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert client.get("/api/v1/metrics/summary").json()["total_requests"] == 1
    assert provider.complete_with_fallback.call_args.kwargs["latency_budget_ms"] > 0


@pytest.mark.parametrize(
    "exc,status",
    [
        (ProviderFailure("secret details"), 502),
        (TimeoutError(), 504),
        (RuntimeError("secret details"), 500),
    ],
)
def test_errors_are_recorded_and_sanitized(client, provider, exc, status):
    provider.complete_with_fallback.side_effect = exc
    response = client.post(
        "/api/v1/chat/completions", json={"messages": [{"role": "user", "content": "Hi"}]}
    )
    assert response.status_code == status
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert "secret details" not in response.text
    stats = client.get("/api/v1/metrics/summary").json()
    assert stats["failed_requests"] == 1
    assert stats["error_rate_pct"] == 100


def test_unavailable(client):
    response = client.post(
        "/api/v1/chat/completions", json={"messages": [{"role": "user", "content": "Hi"}]}
    )
    assert response.status_code == 503


def test_fallback_preserves_routing(client, provider):
    response = client.post(
        "/api/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "Hi"}], "model": "gpt-4"},
    )
    body = response.json()
    assert body["routing"]["model_selected"] == "gpt-4"
    assert body["model_used"] == "claude"
    assert body["fallback_used"]


@pytest.mark.parametrize(
    "patch",
    [
        {"messages": []},
        {"max_tokens": 0},
        {"max_tokens": -1},
        {"latency_budget_ms": -1},
        {"stream": True},
        {"messages": [{"role": "user", "content": "  "}]},
        {"messages": [{"role": "assistant", "content": "hello"}]},
    ],
)
def test_validation(client, patch):
    response = client.post(
        "/api/v1/chat/completions", json={"messages": [{"role": "user", "content": "Hi"}], **patch}
    )
    assert response.status_code == 422


def test_empty_metrics(client):
    assert client.get("/api/v1/metrics/summary").json()["total_requests"] == 0
