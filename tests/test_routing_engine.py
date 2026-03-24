"""
Tests for the routing engine — complexity scoring and model selection.
Run with: pytest tests/ -v
"""

import pytest
from app.services.routing_engine import (
    score_complexity,
    estimate_cost,
    RoutingEngine,
)
from app.models.schemas import ModelChoice


# ---------------------------------------------------------------------------
# Complexity scoring
# ---------------------------------------------------------------------------

class TestComplexityScoring:
    def _msgs(self, text, role="user"):
        return [{"role": role, "content": text}]

    def test_simple_factual_query_is_low_complexity(self):
        result = score_complexity(self._msgs("What is Python?"))
        assert result.score < 0.40, f"Expected low score, got {result.score}"

    def test_code_heavy_query_is_high_complexity(self):
        result = score_complexity(
            self._msgs(
                "Implement a distributed rate limiter in Python using Redis. "
                "Include the class definition, sliding window algorithm, and "
                "async support. ```python"
            )
        )
        assert result.score >= 0.50, f"Expected high score, got {result.score}"

    def test_reasoning_keywords_increase_score(self):
        base = score_complexity(self._msgs("Tell me about neural networks"))
        reasoning = score_complexity(
            self._msgs("Analyze and compare transformer vs RNN architectures, explain why attention mechanisms are superior")
        )
        assert reasoning.score > base.score

    def test_multi_turn_depth_increases_score(self):
        short = [{"role": "user", "content": "hello"}]
        long = [
            {"role": "user", "content": f"message {i}"} for i in range(8)
        ]
        assert score_complexity(long).score > score_complexity(short).score

    def test_score_is_clamped_0_to_1(self):
        giant = self._msgs("analyze explain design implement algorithm code " * 200)
        result = score_complexity(giant)
        assert 0.0 <= result.score <= 1.0

    def test_token_estimate_is_positive(self):
        result = score_complexity(self._msgs("Hello world"))
        assert result.estimated_tokens > 0


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

class TestCostEstimation:
    def test_gpt4_more_expensive_than_claude(self):
        tokens = 1000
        assert estimate_cost(tokens, ModelChoice.GPT4) > estimate_cost(tokens, ModelChoice.CLAUDE)

    def test_cost_scales_with_tokens(self):
        c1 = estimate_cost(100, ModelChoice.CLAUDE)
        c2 = estimate_cost(1000, ModelChoice.CLAUDE)
        assert c2 > c1

    def test_cost_is_non_negative(self):
        assert estimate_cost(0, ModelChoice.GPT4) >= 0


# ---------------------------------------------------------------------------
# Routing decisions
# ---------------------------------------------------------------------------

class TestRoutingEngine:
    def setup_method(self):
        self.engine = RoutingEngine()

    def _msgs(self, text):
        return [{"role": "user", "content": text}]

    def test_simple_query_routes_to_claude(self):
        decision = self.engine.route(self._msgs("What is the capital of France?"))
        assert decision.model_selected == ModelChoice.CLAUDE

    def test_complex_code_query_routes_to_gpt4(self):
        decision = self.engine.route(
            self._msgs(
                "Design and implement a fault-tolerant distributed consensus algorithm "
                "in Python, analyze its time complexity, and compare it against Raft. "
                "Include class definitions, async methods, and explain the CAP theorem tradeoffs. "
                "```python class RaftNode:"
            )
        )
        assert decision.model_selected == ModelChoice.GPT4

    def test_tight_latency_budget_forces_claude(self):
        # Even a complex query should go to Claude with a 500ms budget
        decision = self.engine.route(
            self._msgs("Explain transformers and implement self-attention in Python"),
            latency_budget_ms=500,
        )
        assert decision.model_selected == ModelChoice.CLAUDE

    def test_explicit_model_override_respected(self):
        decision = self.engine.route(
            self._msgs("What is 2+2?"),
            preferred_model=ModelChoice.GPT4,
        )
        assert decision.model_selected == ModelChoice.GPT4

    def test_decision_has_reason(self):
        decision = self.engine.route(self._msgs("Hello"))
        assert len(decision.reason) > 0

    def test_decision_has_cost_estimate(self):
        decision = self.engine.route(self._msgs("Hello world"))
        assert decision.estimated_cost_usd >= 0

    def test_complexity_score_in_decision(self):
        decision = self.engine.route(self._msgs("Hello"))
        assert 0.0 <= decision.complexity_score <= 1.0
