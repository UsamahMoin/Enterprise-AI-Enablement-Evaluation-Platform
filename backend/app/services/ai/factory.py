"""Provider selection.

The rest of the application depends on `get_provider()`, not on a vendor.
"""

from app.core.config import settings
from app.services.ai.base import AIProvider
from app.services.ai.local_provider import LocalProvider
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.stub_provider import StubProvider

_cache: dict[str, AIProvider] = {}


def get_provider(name: str | None = None) -> AIProvider:
    provider_name = name or settings.ai_provider
    if provider_name in _cache:
        return _cache[provider_name]

    if provider_name == "openai":
        provider: AIProvider = OpenAIProvider()
    elif provider_name == "local":
        provider = LocalProvider()
    elif provider_name == "stub":
        provider = StubProvider()
    else:  # pragma: no cover - guarded by settings validation
        raise ValueError(f"Unknown AI provider: {provider_name}")

    _cache[provider_name] = provider
    return provider


def get_judge_provider() -> AIProvider:
    """Provider used for the LLM-as-judge step.

    Defaults to the generation provider. Pointing it at a different one is
    deliberate: a model grading its own output shows self-preference bias.
    """
    return get_provider(settings.judge_provider)


def get_moderation_provider(generation_provider: AIProvider) -> AIProvider | None:
    """Provider used to moderate input.

    The generation provider is used when it can moderate. Otherwise the
    explicitly configured fallback is used, and if there is none, moderation is
    not performed - which the caller must handle rather than assume clean.
    """
    if generation_provider.supports_moderation:
        return generation_provider
    if settings.moderation_provider:
        fallback = get_provider(settings.moderation_provider)
        if fallback.supports_moderation:
            return fallback
    return None


def available_providers() -> list[dict]:
    """Capability summary for the governance screen."""
    summaries = []
    for name in ("stub", "openai", "local"):
        try:
            summaries.append(get_provider(name).capabilities())
        except Exception as exc:  # noqa: BLE001 - unconfigured providers are expected
            summaries.append({"name": name, "configured": False, "error": str(exc)[:160]})
    return summaries


def reset_provider_cache() -> None:
    """Used by tests to swap providers between cases."""
    _cache.clear()
