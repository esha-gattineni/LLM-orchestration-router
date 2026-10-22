"""Provider adapters with bounded fallback and normalized token accounting."""

import asyncio
import time

import anthropic
import openai
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.models.schemas import ModelChoice, UsageStats
from app.services.routing_engine import estimate_cost


class ProviderUnavailable(Exception):
    pass


class ProviderFailure(Exception):
    pass


def retryable(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, openai.APIConnectionError, anthropic.APIConnectionError)):
        return True
    if isinstance(exc, (openai.APIStatusError, anthropic.APIStatusError)):
        return exc.status_code in (408, 429) or exc.status_code >= 500
    return False


def normalize_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text = "".join(
            block if isinstance(block, str) else block.get("text", "")
            for block in content
            if isinstance(block, str) or isinstance(block, dict) and block.get("type") == "text"
        )
        if text:
            return text
    raise ProviderFailure("Provider did not return supported text content")


class LLMClient:
    def __init__(self):
        self._clients = {}

    def available_models(self) -> set[ModelChoice]:
        models = set()
        if settings.OPENAI_API_KEY.strip():
            models.add(ModelChoice.GPT4)
        if settings.ANTHROPIC_API_KEY.strip():
            models.add(ModelChoice.CLAUDE)
        return models

    def _get_llm(self, model):
        if model not in self.available_models():
            raise ProviderUnavailable("Provider is not configured")
        if model not in self._clients:
            if model == ModelChoice.GPT4:
                client = ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    api_key=settings.OPENAI_API_KEY,
                    max_tokens=settings.OPENAI_MAX_TOKENS,
                    max_retries=0,
                    timeout=30,
                )
            else:
                client = ChatAnthropic(
                    model=settings.ANTHROPIC_MODEL,
                    api_key=settings.ANTHROPIC_API_KEY,
                    max_tokens=settings.ANTHROPIC_MAX_TOKENS,
                    max_retries=0,
                    timeout=30,
                )
            self._clients[model] = client
        return self._clients[model]

    async def complete(self, messages, model, max_tokens=None):
        llm = self._get_llm(model)
        cap = (
            settings.OPENAI_MAX_TOKENS
            if model == ModelChoice.GPT4
            else settings.ANTHROPIC_MAX_TOKENS
        )
        if max_tokens is not None:
            llm = llm.bind(max_tokens=min(max_tokens, cap))
        mapping = {"user": HumanMessage, "assistant": AIMessage, "system": SystemMessage}
        start = time.perf_counter()
        response = await llm.ainvoke([mapping[m["role"]](content=m["content"]) for m in messages])
        meta = getattr(response, "response_metadata", {}) or {}
        raw = (
            getattr(response, "usage_metadata", None)
            or meta.get("token_usage")
            or meta.get("usage")
            or {}
        )
        prompt = raw.get("input_tokens", raw.get("prompt_tokens"))
        completion = raw.get("output_tokens", raw.get("completion_tokens"))
        known = all(
            isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in (prompt, completion)
        )
        usage = UsageStats(
            prompt_tokens=prompt if known else None,
            completion_tokens=completion if known else None,
            total_tokens=prompt + completion if known else None,
            cost_usd=estimate_cost(prompt, model, completion) if known else None,
            usage_available=known,
            latency_ms=(time.perf_counter() - start) * 1000,
        )
        return normalize_text(response.content), usage

    async def complete_with_fallback(
        self, messages, primary_model, max_tokens=None, latency_budget_ms=None
    ):
        budget = settings.LATENCY_BUDGET_MS if latency_budget_ms is None else latency_budget_ms
        fallback = ModelChoice.CLAUDE if primary_model == ModelChoice.GPT4 else ModelChoice.GPT4
        can_fallback = settings.FALLBACK_ENABLED and fallback in self.available_models()
        start = time.perf_counter()
        deadline = start + budget / 1000
        models = [primary_model, fallback] if can_fallback else [primary_model]
        for index, model in enumerate(models):
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError("Request deadline exceeded")
            timeout = (
                remaining * settings.PRIMARY_BUDGET_FRACTION
                if index == 0 and can_fallback
                else remaining
            )
            try:
                async with asyncio.timeout(timeout):
                    content, usage = await self.complete(messages, model, max_tokens)
                usage.latency_ms = round((time.perf_counter() - start) * 1000, 2)
                return content, usage, model
            except Exception as exc:
                if retryable(exc) and index + 1 < len(models):
                    continue
                if isinstance(exc, TimeoutError):
                    raise
                if isinstance(exc, (openai.APIError, anthropic.APIError)):
                    raise ProviderFailure("Provider request failed") from exc
                raise
        raise ProviderFailure("No successful provider response")


_client = LLMClient()


def get_llm_client() -> LLMClient:
    return _client
