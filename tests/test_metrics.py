import pytest

from app.models.schemas import ModelChoice
from app.services.metrics_store import MetricsStore, RequestRecord


def test_baseline_uses_actual_token_split():
    store = MetricsStore()
    store.record(RequestRecord(ModelChoice.GPT4, 10, 0.00125, 100, 50))
    assert store.summary()["cost_savings_pct"] == 0


def test_failures_do_not_look_like_free_successes():
    store = MetricsStore()
    store.record(RequestRecord(ModelChoice.CLAUDE, 20, error=True))
    store.record(RequestRecord(ModelChoice.CLAUDE, 10, 0.00105, 100, 50))
    result = store.summary()
    assert result["error_rate_pct"] == 50
    assert result["avg_cost_usd"] == 0.00105
    assert result["cost_savings_pct"] == pytest.approx(16)
