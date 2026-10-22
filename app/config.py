from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
    APP_VERSION: str = "1.1.0"
    APP_ENV: str = "development"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = Field(default=4096, gt=0)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-4-5"
    ANTHROPIC_MAX_TOKENS: int = Field(default=4096, gt=0)
    # USD per million tokens. Supply rates for the exact configured model.
    OPENAI_INPUT_USD_PER_MILLION: float | None = Field(default=None, ge=0)
    OPENAI_OUTPUT_USD_PER_MILLION: float | None = Field(default=None, ge=0)
    ANTHROPIC_INPUT_USD_PER_MILLION: float | None = Field(default=None, ge=0)
    ANTHROPIC_OUTPUT_USD_PER_MILLION: float | None = Field(default=None, ge=0)
    COMPLEXITY_THRESHOLD: float = Field(default=0.65, ge=0, le=1)
    LATENCY_BUDGET_MS: int = Field(default=30000, gt=0, le=300000)
    MAX_TOKEN_COST_RATIO: float = Field(default=1.5, gt=0)
    ESTIMATED_OUTPUT_TOKENS: int = Field(default=256, gt=0)
    FAST_MODEL: Literal["gpt-4", "claude"] = "claude"
    FALLBACK_ENABLED: bool = True
    PRIMARY_BUDGET_FRACTION: float = Field(default=0.65, gt=0, lt=1)


settings = Settings()
