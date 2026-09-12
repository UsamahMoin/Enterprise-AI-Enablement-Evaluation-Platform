"""Deterministic offline provider.

Purpose: the entire platform - execution, evaluation, governance,
analytics - must be runnable by a reviewer with `docker compose up` and no
API key or spend. The stub returns plausible, workflow-shaped output derived
deterministically from the input, so evaluation and dashboards behave
realistically without a network call.

It is NOT a model. It is a fixture with a provider interface.
"""

import hashlib
import json
import random
import time

from app.services.ai.base import (
    AIProvider,
    GenerationRequest,
    GenerationResponse,
    ModerationResult,
)

_MODERATION_TERMS = {"self-harm", "kill myself", "make a bomb", "hate crime"}


def _seed_from(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def _approx_tokens(text: str) -> int:
    # ~4 characters per token is a reasonable public rule of thumb.
    return max(1, len(text) // 4)


class StubProvider(AIProvider):
    name = "stub"

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        started = time.perf_counter()
        rng = random.Random(_seed_from(request.system_prompt + request.user_prompt))

        if request.json_schema is not None:
            text = json.dumps(self._synth_json(request, rng), indent=2)
        else:
            text = self._synth_text(request, rng)

        latency_ms = int((time.perf_counter() - started) * 1000) + rng.randint(700, 2600)
        return GenerationResponse(
            text=text,
            model=request.model,
            provider=self.name,
            input_tokens=_approx_tokens(request.system_prompt + request.user_prompt),
            output_tokens=_approx_tokens(text),
            latency_ms=latency_ms,
        )

    async def moderate(self, text: str) -> ModerationResult:
        lowered = text.lower()
        hits = [term for term in _MODERATION_TERMS if term in lowered]
        return ModerationResult(flagged=bool(hits), categories=hits, provider=self.name)

    # -- synthesis -------------------------------------------------------
    def _synth_json(self, request: GenerationRequest, rng: random.Random) -> dict:
        """Produce an object satisfying the requested schema's top level."""
        schema = request.json_schema or {}
        properties: dict = schema.get("schema", {}).get("properties", {})
        excerpt = request.user_prompt.strip().splitlines()
        first_line = next((line for line in excerpt if line.strip()), "the supplied input")

        out: dict = {}
        for key, spec in properties.items():
            kind = spec.get("type", "string")
            if kind == "array":
                out[key] = self._synth_array(key, spec, first_line, rng)
            elif kind in ("number", "integer"):
                out[key] = rng.randint(78, 96)
            elif kind == "boolean":
                out[key] = True
            else:
                out[key] = f"{key.replace('_', ' ').capitalize()} derived from {first_line[:80]}"
        return out

    def _synth_array(self, key: str, spec: dict, source: str, rng: random.Random) -> list:
        item_spec = spec.get("items", {})
        count = rng.randint(2, 3)
        if item_spec.get("type") == "object":
            props = item_spec.get("properties", {})
            items = []
            for index in range(count):
                obj = {}
                for field_name in props:
                    if "owner" in field_name:
                        obj[field_name] = rng.choice(["A. Rivera", "J. Chen", "M. Okafor"])
                    elif "deadline" in field_name or "date" in field_name:
                        obj[field_name] = f"2026-0{rng.randint(1, 9)}-1{index}"
                    else:
                        obj[field_name] = f"{field_name.replace('_', ' ').capitalize()} {index + 1}"
                items.append(obj)
            return items
        return [f"{key.replace('_', ' ').capitalize()} point {i + 1}: {source[:60]}" for i in range(count)]

    def _synth_text(self, request: GenerationRequest, rng: random.Random) -> str:
        task = request.metadata.get("workflow_slug", "task")
        inputs = request.user_prompt.strip()
        head = inputs.splitlines()[0][:120] if inputs else "the request"

        if "unit_test" in task or "test" in task:
            return (
                "```python\n"
                "import pytest\n\n"
                "from module import calculate_total\n\n\n"
                "def test_calculate_total_happy_path():\n"
                "    assert calculate_total([10, 20, 30]) == 60\n\n\n"
                "def test_calculate_total_empty_input():\n"
                "    assert calculate_total([]) == 0\n\n\n"
                "def test_calculate_total_rejects_negative_values():\n"
                "    with pytest.raises(ValueError):\n"
                "        calculate_total([-1])\n"
                "```\n\n"
                "Edge cases covered: empty collection, negative values, and the\n"
                "standard aggregation path."
            )
        if "support" in task:
            return (
                "Hi there,\n\n"
                "Thanks for flagging this - I'm sorry your account stopped working, "
                "and I appreciate you taking the time to report it.\n\n"
                "So I can resolve this quickly, could you confirm:\n"
                "1. The email address on the account\n"
                "2. The exact error message you see at sign-in\n"
                "3. Whether the issue persists in a private browser window\n\n"
                "Per our published support policy, account access issues are "
                "prioritised and we aim to respond within one business day.\n\n"
                "Best regards,\nCustomer Support"
            )
        if "variance" in task or "finance" in task:
            return (
                "Summary\n"
                f"Actual spend exceeded budget, driven by the items described in {head}.\n\n"
                "Drivers\n"
                "- Marketing spend increased by $45,000 against plan.\n"
                "- Infrastructure increased by $25,000 against plan.\n\n"
                "Recommendations\n"
                "- Confirm whether the marketing overage was campaign timing or rate.\n"
                "- Review infrastructure commitments before the next cycle.\n\n"
                "Figures above are taken from the supplied variance report only."
            )
        if "job_description" in task or "hr" in task:
            return (
                "Revised description\n"
                "We are hiring a practitioner who will own delivery for this area.\n\n"
                "Responsibilities\n"
                "- Deliver and maintain the core work of the team\n"
                "- Partner with adjacent functions\n\n"
                "Requirements\n"
                "- Demonstrated experience in the relevant discipline\n\n"
                "Notes on inclusive language\n"
                "- Replaced 'young, energetic' with experience-based criteria.\n"
                "- Removed 'rockstar' in favour of a concrete responsibility."
            )
        return (
            "Summary\n"
            f"{head}\n\n"
            "Key points\n"
            f"- Point one derived from the supplied input.\n"
            f"- Point two derived from the supplied input.\n\n"
            "Recommendations\n"
            "- Next step one.\n"
            "- Next step two."
        )
