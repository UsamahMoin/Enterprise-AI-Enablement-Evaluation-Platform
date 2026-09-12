"""Level 2 evaluation: LLM-as-judge.

A second model call scores the first output against a rubric and must return
structured JSON - never free prose. The judge is treated as a *signal*, not
as ground truth; human feedback is collected separately and compared against
it on the quality dashboard.
"""

import json

from app.core.config import settings
from app.services.ai.base import AIProvider, GenerationRequest
from app.services.evaluation.deterministic import extract_json

JUDGE_SYSTEM_PROMPT = """You are a strict evaluator of AI-generated work inside an enterprise \
platform. You score a candidate response against a task and, where provided, against \
reference material.

Rules:
- Score each requested dimension from 0 to 100.
- Judge only what is present. Do not rewrite or improve the response.
- Groundedness measures whether every factual claim is supported by the REFERENCE \
MATERIAL. If no reference material is supplied, return null for groundedness rather \
than guessing.
- Be concise in your reasoning: at most three sentences.
- Return JSON only."""

JUDGE_TEMPLATE = """TASK
{task}

INPUT PROVIDED BY THE USER
{user_input}

REFERENCE MATERIAL
{reference}

CANDIDATE RESPONSE
{output}

RUBRIC
Score these dimensions: {dimensions}
{criteria}
"""


def _schema(dimensions: list[str]) -> dict:
    properties: dict = {
        dimension: {"type": ["number", "null"], "description": f"{dimension} score 0-100"}
        for dimension in dimensions
    }
    properties["reasoning"] = {"type": "string"}
    return {
        "name": "evaluation",
        "schema": {
            "type": "object",
            "properties": properties,
            "required": [*dimensions, "reasoning"],
            "additionalProperties": False,
        },
    }


async def judge_output(
    provider: AIProvider,
    *,
    task: str,
    user_input: str,
    output: str,
    dimensions: list[str],
    reference: str = "",
    criteria: list[str] | None = None,
    model: str | None = None,
) -> dict:
    """Return {dimension: score|None, "reasoning": str, "model": str}."""
    if not dimensions:
        return {"reasoning": "", "model": ""}

    has_reference = bool(reference and reference.strip())
    scored_dimensions = [
        dimension
        for dimension in dimensions
        if dimension != "groundedness" or has_reference
    ]
    if not scored_dimensions:
        return {"reasoning": "No dimensions applicable.", "model": ""}

    criteria_text = ""
    if criteria:
        criteria_text = "Additional criteria:\n" + "\n".join(f"- {item}" for item in criteria)

    prompt = JUDGE_TEMPLATE.format(
        task=task,
        user_input=user_input[:6000],
        reference=reference[:6000] if has_reference else "(none supplied)",
        output=output[:8000],
        dimensions=", ".join(scored_dimensions),
        criteria=criteria_text,
    )

    judge_model = model or settings.evaluation_model
    response = await provider.generate(
        GenerationRequest(
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=prompt,
            model=judge_model,
            temperature=0.0,
            max_output_tokens=600,
            json_schema=_schema(scored_dimensions),
            metadata={"purpose": "evaluation"},
        )
    )

    parsed = extract_json(response.text)
    if not isinstance(parsed, dict):
        return {
            "reasoning": "Judge returned unparseable output; model-based scores omitted.",
            "model": judge_model,
        }

    result: dict = {"model": judge_model, "reasoning": str(parsed.get("reasoning", ""))[:2000]}
    for dimension in scored_dimensions:
        value = parsed.get(dimension)
        if isinstance(value, (int, float)):
            result[dimension] = max(0.0, min(100.0, float(value)))
        else:
            result[dimension] = None
    if "groundedness" not in result:
        result["groundedness"] = None
    return result


def serialise_reference(inputs: dict, grounding_fields: list[str]) -> str:
    """Concatenate the input fields a workflow treats as source of truth."""
    parts = []
    for field in grounding_fields or []:
        value = (inputs or {}).get(field)
        if isinstance(value, str) and value.strip():
            parts.append(f"--- {field} ---\n{value.strip()}")
    return "\n\n".join(parts)


def dumps(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True)
