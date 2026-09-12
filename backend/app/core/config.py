"""Application settings, loaded from the environment.

Secrets (database URL, JWT secret, provider API keys) are never hard-coded:
they are read from environment variables so that the same image can be
promoted across environments.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://eail:eail_dev_password@localhost:5432/eail"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    demo_password: str = "demo1234"

    # AI provider. "stub" keeps the whole platform runnable with deterministic
    # offline responses so the demo works without an API key or spend.
    ai_provider: Literal["stub", "openai", "local"] = "stub"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4.1-mini"
    evaluation_model: str = "gpt-4.1-mini"

    # Provider used for the LLM-as-judge step. Defaults to the generation
    # provider. Setting it to a *different* provider is the point: a model
    # grading its own output shows self-preference bias, and an independent
    # judge is a cheap mitigation. It also lets sensitive output be evaluated
    # locally while generation stays hosted, or the reverse.
    evaluation_provider: Literal["", "stub", "openai", "local"] = ""

    # Self-hosted inference, served over an OpenAI-compatible API
    # (Ollama: http://localhost:11434/v1, LM Studio: http://localhost:1234/v1).
    local_ai_base_url: str = "http://localhost:11434/v1"
    local_ai_model: str = "qwen3:8b"
    local_ai_api_key: str = ""
    # Local inference is slow on modest hardware; the timeout reflects that.
    local_request_timeout_seconds: float = 300.0

    # Provider used for moderation when the generation provider cannot
    # moderate. Leave empty to perform no moderation in that case - the result
    # is then recorded as "not checked", never as "passed".
    moderation_provider: Literal["", "stub", "openai", "local"] = ""
    # When true, a blocking moderation policy rejects requests it could not
    # check. Off by default so the offline demo runs; documented as the setting
    # a regulated deployment would turn on.
    moderation_fail_closed: bool = False

    # Generation defaults
    request_timeout_seconds: float = 60.0

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def provider_configured(self) -> bool:
        if self.ai_provider == "openai":
            return bool(self.openai_api_key)
        # "stub" needs nothing; "local" needs a reachable server, which is
        # checked at call time rather than from configuration alone.
        return True

    @property
    def judge_provider(self) -> str:
        return self.evaluation_provider or self.ai_provider


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
