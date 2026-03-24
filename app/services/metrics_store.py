"""
Metrics Store
-------------
Thread-safe in-memory store for routing and cost metrics.
Flushes to Application Insights periodically and exposes a
summary endpoint for dashboards / alerting.
"""

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from app.models.schemas import ModelChoice


@dataclass
class RequestRecord:
    model: ModelChoice
    latency_ms: float
    cost_usd: float
    tokens: int
    complexity_score: float
    error: bool = False
    timestamp: float = field(default_factory=time.time)


class MetricsStore:
    _MAX_RECORDS = 10_000  # rolling window

    def __init__(self):
        self._lock = threading.Lock()
        self._records: Deque[RequestRecord] = deque(maxlen=self._MAX_RECORDS)

    def record(self, req: RequestRecord):
        with self._lock:
            self._records.append(req)

    def summary(self) -> dict:
        with self._lock:
            records = list(self._records)

        if not records:
            return {
                "total_requests": 0,
                "gpt4_requests": 0,
                "claude_requests": 0,
                "avg_latency_ms": 0,
                "avg_cost_usd": 0,
                "total_cost_usd": 0,
                "cost_savings_pct": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
                "error_rate_pct": 0,
            }

        gpt4 = [r for r in records if r.model == ModelChoice.GPT4]
        claude = [r for r in records if r.model == ModelChoice.CLAUDE]
        latencies = sorted(r.latency_ms for r in records)
        costs = [r.cost_usd for r in records]
        errors = sum(1 for r in records if r.error)

        total = len(records)
        n = len(latencies)

        # Hypothetical cost if every request had used GPT-4
        from app.services.routing_engine import estimate_cost
        baseline_cost = sum(
            estimate_cost(r.tokens, ModelChoice.GPT4) for r in records
        )
        actual_cost = sum(costs)
        savings_pct = (
            round((baseline_cost - actual_cost) / baseline_cost * 100, 2)
            if baseline_cost > 0
            else 0
        )

        return {
            "total_requests": total,
            "gpt4_requests": len(gpt4),
            "claude_requests": len(claude),
            "avg_latency_ms": round(sum(latencies) / n, 2),
            "avg_cost_usd": round(sum(costs) / total, 6),
            "total_cost_usd": round(actual_cost, 4),
            "cost_savings_pct": savings_pct,
            "p95_latency_ms": round(latencies[math.ceil(n * 0.95) - 1], 2),
            "p99_latency_ms": round(latencies[math.ceil(n * 0.99) - 1], 2),
            "error_rate_pct": round(errors / total * 100, 2),
        }


_store: MetricsStore | None = None


def get_metrics_store() -> MetricsStore:
    global _store
    if _store is None:
        _store = MetricsStore()
    return _store
