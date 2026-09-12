"""OpenAI implementation of the AIProvider interface.

Uses the Responses API and the Moderations endpoint. The API key is read
from configuration (environment), never from application code.
"""

import time

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.ai.base import (
    AIProvider,
    GenerationRequest,
    GenerationResponse,
    ModerationResult,
)


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        key = api_key or settings.openai_api_key
        if not key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Set AI_PROVIDER=stub to run without a key."
            )
        kwargs: dict = {"api_key": key, "timeout": settings.request_timeout_seconds}
        url = base_url or settings.openai_base_url
        if url:
            kwargs["base_url"] = url
        self._client = AsyncOpenAI(**kwargs)

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        started = time.perf_counter()

        kwargs: dict = {
            "model": request.model,
            "instructions": request.system_prompt,
            "input": request.user_prompt,
            "temperature": request.temperature,
            "max_output_tokens": request.max_output_tokens,
        }
        if request.json_schema is not None:
            kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.json_schema.get("name", "response"),
                    "schema": request.json_schema["schema"],
                    "strict": True,
                }
            }

        response = await self._client.responses.create(**kwargs)
        latency_ms = int((time.perf_counter() - started) * 1000)

        usage = getattr(response, "usage", None)
        return GenerationResponse(
            text=response.output_text or "",
            model=request.model,
            provider=self.name,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            latency_ms=latency_ms,
        )

    async def moderate(self, text: str) -> ModerationResult:
        result = await self._client.moderations.create(
            model="omni-moderation-latest", input=text
        )
        item = result.results[0]
        flagged_categories = [
            name
            for name, value in item.categories.model_dump().items()
            if value
        ]
        return ModerationResult(
            flagged=bool(item.flagged), categories=flagged_categories, provider=self.name
        )
