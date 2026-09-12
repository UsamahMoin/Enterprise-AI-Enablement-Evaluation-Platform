"""Provider-agnostic AI interface.

Every model call in the platform goes through this interface. No route,
repository or evaluator imports a vendor SDK directly, so adding Anthropic
Claude later is a new subclass plus a factory entry - not a refactor.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GenerationRequest:
    system_prompt: str
    user_prompt: str
    model: str
    temperature: float = 0.2
    max_output_tokens: int = 1500
    # When set, the provider is asked to return JSON matching this shape.
    json_schema: dict | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class GenerationResponse:
    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    raw: dict = field(default_factory=dict)


@dataclass
class ModerationResult:
    flagged: bool
    categories: list[str] = field(default_factory=list)
    provider: str = ""


class AIProvider(ABC):
    """Contract implemented by every model vendor."""

    name: str = "base"

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Produce a completion for the given request."""
        raise NotImplementedError

    async def moderate(self, text: str) -> ModerationResult:
        """Screen text for harmful content. Providers without a moderation
        endpoint may fall back to a permissive result."""
        return ModerationResult(flagged=False, provider=self.name)
