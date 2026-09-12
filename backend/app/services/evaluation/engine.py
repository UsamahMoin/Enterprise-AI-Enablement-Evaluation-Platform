"""Orchestrates the three evaluation layers for a single execution.

    Level 1  deterministic checks   (free, reproducible, run always)
    Level 2  LLM-as-judge            (scaled qualitative signal)
    Level 3  human feedback          (collected separately, never inferred)

Levels 1 and 2 run here. Level 3 arrives later via the feedback endpoint.
"""

from dataclasses import dataclass, field

from app.services.ai.base import AIProvider
from app.services.evaluation.deterministic import (
    CheckResult,
    format_compliance_score,
    run_deterministic_checks,
)
from app.services.evaluation.judge import judge_output, serialise_reference
from app.services.evaluation.scoring import compute_overall

DEFAULT_JUDGE_DIMENSIONS = ["relevance", "completeness", "clarity", "groundedness"]


@dataclass
class EvaluationOutcome:
    relevance: float | None = None
    completeness: float | None = None
    groundedness: float | None = None
    clarity: float | None = None
    format_compliance: float | None = None
    safety_passed: bool = True
    overall_score: float = 0.0
    deterministic_checks: list[CheckResult] = field(default_factory=list)
    evaluation_model: str = ""
    evaluation_reasoning: str = ""
    rubric_used: dict = field(default_factory=dict)


async def evaluate(
    provider: AIProvider,
    *,
    task: str,
    inputs: dict,
    output: str,
    rubric: dict,
    use_judge: bool = True,
) -> EvaluationOutcome:
    rubric = rubric or {}
    outcome = EvaluationOutcome(rubric_used=rubric)

    # --- Level 1: deterministic -----------------------------------------
    checks = run_deterministic_checks(output, rubric.get("deterministic", {}))
    outcome.deterministic_checks = checks
    outcome.format_compliance = format_compliance_score(checks)

    # --- Safety ----------------------------------------------------------
    moderation = await provider.moderate(output or "")
    outcome.safety_passed = not moderation.flagged

    # --- Level 2: model-based -------------------------------------------
    if use_judge:
        reference = serialise_reference(inputs, rubric.get("grounding_fields", []))
        judged = await judge_output(
            provider,
            task=task,
            user_input="\n".join(f"{k}: {v}" for k, v in (inputs or {}).items()),
            output=output,
            dimensions=rubric.get("judge_dimensions", DEFAULT_JUDGE_DIMENSIONS),
            reference=reference,
            criteria=rubric.get("criteria", []),
            model=rubric.get("evaluation_model"),
        )
        outcome.relevance = judged.get("relevance")
        outcome.completeness = judged.get("completeness")
        outcome.clarity = judged.get("clarity")
        outcome.groundedness = judged.get("groundedness")
        outcome.evaluation_model = judged.get("model", "")
        outcome.evaluation_reasoning = judged.get("reasoning", "")

    outcome.overall_score = compute_overall(
        {
            "relevance": outcome.relevance,
            "completeness": outcome.completeness,
            "groundedness": outcome.groundedness,
            "clarity": outcome.clarity,
            "format_compliance": outcome.format_compliance,
        },
        rubric.get("weights"),
        safety_passed=outcome.safety_passed,
    )
    return outcome
