"""API settings, read from environment variables."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every setting the API needs. Field names map to UPPER_CASE env vars."""

    model_config = SettingsConfigDict(extra="ignore")

    # Cube REST API (the only way this service reads metrics).
    cube_api_url: str = "http://localhost:4000/cubejs-api/v1"
    cubejs_api_secret: SecretStr
    cube_timeout_seconds: float = Field(default=20.0, gt=0)

    # LLM (free tiers only).
    llm_provider: Literal["gemini", "groq", "ollama"] = "groq"
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    llm_timeout_seconds: float = Field(default=30.0, gt=0)

    # Abuse limits for /ask.
    ask_max_question_chars: int = Field(default=300, ge=20)
    ask_rate_per_minute: int = Field(default=6, ge=1)
    ask_daily_limit: int = Field(default=500, ge=1)

    # Live KPI stream.
    sse_interval_seconds: float = Field(default=10.0, ge=2)

    # Browser origins allowed to call the API (comma separated), e.g. the website.
    web_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    def allowed_origins(self) -> list[str]:
        """Parse WEB_ORIGINS into a list."""
        return [origin.strip() for origin in self.web_origins.split(",") if origin.strip()]
