"""
Integration tests for the FastAPI endpoints.
Requires no real API keys — LLM calls are mocked.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import ModelChoice, UsageStats


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_usage():
    return UsageStats(
        prompt_tokens=50,
        completion_tokens=100,
        total_tokens=150,
        cost_usd=0.0012,
        latency_ms=320.0,
    )


class TestHealthEndpoints:
    def test_liveness(self, client):
        resp = client.get("/health/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_readiness(self, client):
        resp = client.get("/health/ready")
        assert resp.status_code == 200


class TestChatEndpoint:
    def test_routes_and_returns_200(self, client, mock_usage):
        with patch(
            "app.routers.chat.get_llm_client"
        ) as mock_client_factory:
            mock_client = MagicMock()
            mock_client.complete_with_fallback = AsyncMock(
                return_value=("Hello! I can help with that.", mock_usage, ModelChoice.CLAUDE)
            )
            mock_client_factory.return_value = mock_client

            resp = client.post(
                "/api/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "What is Python?"}],
                    "model": "auto",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert "routing" in body
        assert "usage" in body
        assert "request_id" in body

    def test_explicit_model_selection(self, client, mock_usage):
        with patch("app.routers.chat.get_llm_client") as mock_client_factory:
            mock_client = MagicMock()
            mock_client.complete_with_fallback = AsyncMock(
                return_value=("GPT-4 response", mock_usage, ModelChoice.GPT4)
            )
            mock_client_factory.return_value = mock_client

            resp = client.post(
                "/api/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model": "gpt-4",
                },
            )

        assert resp.status_code == 200

    def test_returns_request_id_header(self, client, mock_usage):
        with patch("app.routers.chat.get_llm_client") as mock_client_factory:
            mock_client = MagicMock()
            mock_client.complete_with_fallback = AsyncMock(
                return_value=("Response", mock_usage, ModelChoice.CLAUDE)
            )
            mock_client_factory.return_value = mock_client

            resp = client.post(
                "/api/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hi"}]},
            )

        assert "X-Request-ID" in resp.headers


class TestMetricsEndpoint:
    def test_empty_metrics_returns_zeros(self, client):
        resp = client.get("/api/v1/metrics/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_requests"] == 0
