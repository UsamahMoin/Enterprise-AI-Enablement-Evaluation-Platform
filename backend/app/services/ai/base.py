"""Provider-agnostic AI interface.

Every model call in the platform goes through this interface. No route,
repository or evaluator imports a vendor SDK directly, so adding a provider is
a new subclass plus a factory entry - not a refactor.

Providers also declare *capabilities*, because they are not interchangeable in
the ways governance cares about. A self-hosted model keeps data inside the
network but has no moderation endpoint; a hosted frontier model moderates well
but is an egress of data. The governance layer reads these declarations rather
than hard-coding vendor names.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.enums import DataClassification


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
    # False when the provider cannot moderate at all. A caller must not read
    # `flagged is False` as "this text was checked and is clean".
    available: bool = True


class AIProvider(ABC):
    """Contract implemented by every model backend."""

    name: str = "base"

    #: Whether this provider can screen text for harmful content.
    supports_moderation: bool = False

    #: Highest data classification this provider may receive. A hosted provider
    #: is an egress of data and is capped below a self-hosted one.
    max_data_classification: DataClassification = DataClassification.CONFIDENTIAL

    #: True when inference happens inside the organisation's own network.
    keeps_data_in_house: bool = False

    #: Human-readable note shown in the governance UI.
    description: str = ""

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Produce a completion for the given request."""
        raise NotImplementedError

    async def moderate(self, text: str) -> ModerationResult:
        """Screen text for harmful content.

        The default reports that moderation was *not performed*. It deliberately
        does not return a clean result: a provider with no moderation endpoint
        must not be able to look like one that checked and found nothing.
        """
        return ModerationResult(flagged=False, provider=self.name, available=False)

    def capabilities(self) -> dict:
        return {
            "name": self.name,
            "supports_moderation": self.supports_moderation,
            "max_data_classification": str(self.max_data_classification),
            "keeps_data_in_house": self.keeps_data_in_house,
            "description": self.description,
        }
