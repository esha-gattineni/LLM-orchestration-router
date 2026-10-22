import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

from app.config import settings
from app.services import metrics_store


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(metrics_store, "_store", metrics_store.MetricsStore())
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        monkeypatch.setattr(settings, key, "")
    monkeypatch.setattr(settings, "OPENAI_INPUT_USD_PER_MILLION", 5.0)
    monkeypatch.setattr(settings, "OPENAI_OUTPUT_USD_PER_MILLION", 15.0)
    monkeypatch.setattr(settings, "ANTHROPIC_INPUT_USD_PER_MILLION", 3.0)
    monkeypatch.setattr(settings, "ANTHROPIC_OUTPUT_USD_PER_MILLION", 15.0)
    monkeypatch.setattr(settings, "COMPLEXITY_THRESHOLD", 0.65)
    monkeypatch.setattr(settings, "LATENCY_BUDGET_MS", 30000)
    monkeypatch.setattr(settings, "FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "PRIMARY_BUDGET_FRACTION", 0.65)
    monkeypatch.setattr(settings, "FAST_MODEL", "claude")
