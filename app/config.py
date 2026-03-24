from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Azure Application Insights
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""

    # OpenAI / GPT-4
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = 4096

    # Anthropic / Claude
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-4-5"
    ANTHROPIC_MAX_TOKENS: int = 4096

    # Routing thresholds
    COMPLEXITY_THRESHOLD: float = 0.65       # Above this → GPT-4; below → Claude
    LATENCY_BUDGET_MS: int = 3000            # Max acceptable latency in ms
    MAX_TOKEN_COST_RATIO: float = 1.5        # Cost ratio before forcing cheaper model
    FALLBACK_MODEL: str = "claude"           # Which model to fall back to on error

    # Rate limits
    REQUESTS_PER_MINUTE: int = 500
    BURST_LIMIT: int = 50

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
