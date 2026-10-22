from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ModelChoice(str, Enum):
    GPT4 = "gpt-4"
    CLAUDE = "claude"
    AUTO = "auto"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=100000)

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message content must not be blank")
        return value


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    model: ModelChoice = ModelChoice.AUTO
    max_tokens: int | None = Field(default=None, gt=0, le=32768)
    latency_budget_ms: int | None = Field(default=None, gt=0, le=300000)
    stream: Literal[False] = False

    @model_validator(mode="after")
    def validate_conversation(self):
        if self.messages[-1].role != "user":
            raise ValueError("The last message must have role user")
        if any(m.role == "system" for m in self.messages[1:]):
            raise ValueError("A system message is only allowed at the beginning")
        if sum(len(m.content) for m in self.messages) > 200000:
            raise ValueError("Conversation exceeds 200000 characters")
        return self


class RoutingDecision(BaseModel):
    model_selected: ModelChoice
    complexity_score: float = Field(ge=0, le=1)
    estimated_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    estimated_cost_usd: float | None
    latency_budget_ms: int
    reason: str


class UsageStats(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: float = Field(ge=0)
    usage_available: bool = False


class ChatResponse(BaseModel):
    request_id: str
    content: str
    model_used: ModelChoice
    fallback_used: bool
    routing: RoutingDecision
    usage: UsageStats


class MetricsSummary(BaseModel):
    total_requests: int
    gpt4_requests: int
    claude_requests: int
    failed_requests: int
    fallback_requests: int
    priced_requests: int
    avg_latency_ms: float
    avg_cost_usd: float | None
    total_cost_usd: float | None
    cost_savings_pct: float | None
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate_pct: float
    scope: str = "process-local rolling window of at most 10000 chat requests"
