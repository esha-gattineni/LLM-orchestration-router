from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


class ModelChoice(str, Enum):
    GPT4 = "gpt-4"
    CLAUDE = "claude"
    AUTO = "auto"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: ModelChoice = ModelChoice.AUTO
    max_tokens: Optional[int] = None
    latency_budget_ms: Optional[int] = None   # Override default latency budget
    stream: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [{"role": "user", "content": "Explain how transformers work in ML."}],
                "model": "auto",
                "latency_budget_ms": 3000,
            }
        }


class RoutingDecision(BaseModel):
    model_selected: ModelChoice
    complexity_score: float = Field(..., ge=0.0, le=1.0)
    estimated_tokens: int
    estimated_cost_usd: float
    latency_budget_ms: int
    reason: str


class UsageStats(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float


class ChatResponse(BaseModel):
    request_id: str
    content: str
    model_used: ModelChoice
    routing: RoutingDecision
    usage: UsageStats


class MetricsSummary(BaseModel):
    total_requests: int
    gpt4_requests: int
    claude_requests: int
    avg_latency_ms: float
    avg_cost_usd: float
    total_cost_usd: float
    cost_savings_pct: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate_pct: float
