"""Self-hosted model provider.

Talks to any OpenAI-compatible local server - Ollama, LM Studio, llama.cpp's
server, vLLM - so the platform can run inference without data leaving the
network.

Two things make this a genuinely different implementation rather than the
OpenAI provider with a different URL, which is the point of having an interface:

* It uses **Chat Completions**, not the Responses API. Local servers implement
  the older surface.
* It has **no moderation endpoint**, so it declares `supports_moderation =
  False` and the governance layer handles the gap explicitly instead of
  silently treating unchecked input as clean.

Structured output is requested as `json_object` with the schema described in
the prompt, rather than strict `json_schema`. Smaller local models comply with
the looser form far more reliably, and the judge already parses tolerantly.
"""

import json
import time

from openai import APIConnectionError, APIStatusError, AsyncOpenAI

from app.core.config import settings
from app.core.enums import DataClassification
from app.services.ai.base import (
    AIProvider,
    GenerationRequest,
    GenerationResponse,
    ModerationResult,
)


class LocalProviderUnavailable(RuntimeError):
    """The configured local inference server could not be reached."""


class LocalProvider(AIProvider):
    name = "local"

    # No moderation endpoint exists on local runtimes.
    supports_moderation = False
    # Inference happens on infrastructure the organisation controls, so this is
    # the only provider cleared for RESTRICTED data.
    max_data_classification = DataClassification.RESTRICTED
    keeps_data_in_house = True
    description = (
        "Self-hosted model served over an OpenAI-compatible API. Input never "
        "leaves the network, and there is no moderation endpoint."
    )

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.local_ai_base_url).rstrip("/")
        self.default_model = model or settings.local_ai_model
        self._client = AsyncOpenAI(
            base_url=self.base_url,
            # Local servers ignore the key but the SDK requires one.
            api_key=settings.local_ai_api_key or "not-needed",
            timeout=settings.local_request_timeout_seconds,
            max_retries=0,
        )

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        started = time.perf_counter()

        system_prompt = request.system_prompt
        kwargs: dict = {}
        if request.json_schema is not None:
            # Describe the shape in the prompt and ask for any JSON object.
            # Strict schema enforcement is inconsistent across local runtimes.
            schema = request.json_schema.get("schema", request.json_schema)
            system_prompt = (
                f"{system_prompt}\n\n"
                "Respond with a single JSON object and nothing else - no prose, "
                "no markdown fence. It must match this JSON Schema:\n"
                f"{json.dumps(schema)}"
            )
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await self._client.chat.completions.create(
                model=request.model or self.default_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
                temperature=request.temperature,
                max_tokens=request.max_output_tokens,
                **kwargs,
            )
        except APIConnectionError as exc:
            raise LocalProviderUnavailable(
                f"No local inference server responded at {self.base_url}. "
                "Start one (e.g. `ollama serve`) or set AI_PROVIDER to another value."
            ) from exc
        except APIStatusError as exc:
            raise LocalProviderUnavailable(
                f"Local inference server returned {exc.status_code}: "
                f"{str(exc)[:200]}"
            ) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        choice = response.choices[0] if response.choices else None
        text = (choice.message.content if choice and choice.message else "") or ""

        usage = getattr(response, "usage", None)
        return GenerationResponse(
            text=text.strip(),
            model=response.model or request.model,
            provider=self.name,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
        )

    async def moderate(self, text: str) -> ModerationResult:
        """Not available. Reported as unperformed, never as clean."""
        return ModerationResult(flagged=False, provider=self.name, available=False)

    async def health(self) -> dict:
        """Best-effort reachability check for the governance screen."""
        try:
            models = await self._client.models.list()
            available = [model.id for model in models.data][:20]
            return {
                "reachable": True,
                "base_url": self.base_url,
                "default_model": self.default_model,
                "models": available,
                "default_model_present": self.default_model in available,
            }
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a status
            return {
                "reachable": False,
                "base_url": self.base_url,
                "default_model": self.default_model,
                "models": [],
                "error": str(exc)[:200],
            }
