"""
LLM Client Service
------------------
Thin LangChain wrapper that normalises GPT-4 and Claude into a single
async call interface.  Handles retries, timeout enforcement, and per-model
token accounting.
"""

import time

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from app.config import settings
from app.models.schemas import ModelChoice, UsageStats
from app.services.telemetry import get_telemetry


def _to_langchain_messages(messages: list[dict]):
    mapping = {"user": HumanMessage, "assistant": AIMessage, "system": SystemMessage}
    return [mapping[m["role"]](content=m["content"]) for m in messages]


class LLMClient:
    def __init__(self):
        self._gpt4 = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=0.7,
            request_timeout=30,
        )
        self._claude = ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=settings.ANTHROPIC_MAX_TOKENS,
            temperature=0.7,
            timeout=30,
        )
        self._parser = StrOutputParser()

    def _get_llm(self, model: ModelChoice):
        return self._gpt4 if model == ModelChoice.GPT4 else self._claude

    async def complete(
        self,
        messages: list[dict],
        model: ModelChoice,
        max_tokens: int | None = None,
    ) -> tuple[str, UsageStats]:
        """Run a single completion and return (content, usage)."""
        llm = self._get_llm(model)
        lc_messages = _to_langchain_messages(messages)

        if max_tokens:
            llm = llm.bind(max_tokens=max_tokens)

        t0 = time.perf_counter()
        try:
            response = await llm.ainvoke(lc_messages)
        except Exception as exc:
            get_telemetry().track_exception(exc)
            raise

        latency_ms = (time.perf_counter() - t0) * 1000

        # Extract token usage (LangChain surfaces it via response_metadata)
        meta = getattr(response, "response_metadata", {}) or {}
        usage_raw = meta.get("token_usage") or meta.get("usage") or {}

        prompt_tokens = usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens", 0)
        completion_tokens = (
            usage_raw.get("completion_tokens") or usage_raw.get("output_tokens", 0)
        )
        total_tokens = prompt_tokens + completion_tokens

        from app.services.routing_engine import PRICING
        p = PRICING[model]
        cost = round(
            (prompt_tokens * p["input"] + completion_tokens * p["output"]) / 1000, 6
        )

        usage = UsageStats(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            latency_ms=round(latency_ms, 2),
        )
        return response.content, usage

    async def complete_with_fallback(
        self,
        messages: list[dict],
        primary_model: ModelChoice,
        max_tokens: int | None = None,
    ) -> tuple[str, UsageStats, ModelChoice]:
        """
        Try primary model; fall back to the other on failure.
        Returns (content, usage, actual_model_used).
        """
        fallback = (
            ModelChoice.CLAUDE
            if primary_model == ModelChoice.GPT4
            else ModelChoice.GPT4
        )
        try:
            content, usage = await self.complete(messages, primary_model, max_tokens)
            return content, usage, primary_model
        except Exception:
            get_telemetry().track_event(
                "ModelFallback",
                {"from": primary_model.value, "to": fallback.value},
            )
            content, usage = await self.complete(messages, fallback, max_tokens)
            return content, usage, fallback


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client