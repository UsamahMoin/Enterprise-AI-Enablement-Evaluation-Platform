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
    ai_provider: Literal["stub", "openai"] = "stub"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4.1-mini"
    evaluation_model: str = "gpt-4.1-mini"

    # Generation defaults
    request_timeout_seconds: float = 60.0

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def provider_configured(self) -> bool:
        return self.ai_provider == "stub" or bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
