"""Provider selection.

The rest of the application depends on `get_provider()`, not on a vendor.
"""

from app.core.config import settings
from app.services.ai.base import AIProvider
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.stub_provider import StubProvider

_cache: dict[str, AIProvider] = {}


def get_provider(name: str | None = None) -> AIProvider:
    provider_name = name or settings.ai_provider
    if provider_name in _cache:
        return _cache[provider_name]

    if provider_name == "openai":
        provider: AIProvider = OpenAIProvider()
    elif provider_name == "stub":
        provider = StubProvider()
    else:  # pragma: no cover - guarded by settings validation
        raise ValueError(f"Unknown AI provider: {provider_name}")

    _cache[provider_name] = provider
    return provider


def reset_provider_cache() -> None:
    """Used by tests to swap providers between cases."""
    _cache.clear()
