"""Run the benchmark cases in seed/evaluation_cases.json against a prompt version.

This is what turns "I improved the prompt" into evidence. The same fixed set
of inputs - normal, excellent, poor, ambiguous, adversarial, sensitive and
malformed - is run against each version, so two versions are compared on
identical work rather than on whatever traffic happened to arrive.

Cases marked `expected_behaviour: block` are scored on whether governance
stopped them, not on output quality.
"""

import json
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.paths import SEED_DIR
from app.models.user import User
from app.models.workflow import Workflow, WorkflowVersion
from app.services.ai import GenerationRequest, estimate_cost, get_provider
from app.services.evaluation import evaluate
from app.services.execution_service import render_prompt
from app.services.governance import evaluate_request

CASES_PATH = SEED_DIR / "evaluation_cases.json"


def load_cases(workflow_slug: str | None = None) -> list[dict]:
    payload = json.loads(CASES_PATH.read_text())
    cases = payload["cases"]
    if workflow_slug:
        cases = [case for case in cases if case["workflow"] == workflow_slug]
    return cases


@dataclass
class CaseResult:
    case_id: str
    case_type: str
    expected_behaviour: str
    blocked: bool = False
    passed_expectation: bool = True
    overall_score: float | None = None
    relevance: float | None = None
    completeness: float | None = None
    groundedness: float | None = None
    format_compliance: float | None = None
    deterministic: list[dict] = field(default_factory=list)
    latency_ms: int = 0
    estimated_cost: float = 0.0
    reasoning: str = ""
    error: str = ""


@dataclass
class VersionBenchmark:
    version: int
    model: str
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def scored(self) -> list[CaseResult]:
        return [case for case in self.cases if case.overall_score is not None]

    def _mean(self, attribute: str) -> float | None:
        values = [
            getattr(case, attribute)
            for case in self.scored
            if getattr(case, attribute) is not None
        ]
        return round(sum(values) / len(values), 1) if values else None

    def summary(self) -> dict:
        blocking_cases = [c for c in self.cases if c.expected_behaviour == "block"]
        return {
            "version": self.version,
            "model": self.model,
            "cases_run": len(self.cases),
            "cases_scored": len(self.scored),
            "average_quality": self._mean("overall_score"),
            "relevance": self._mean("relevance"),
            "completeness": self._mean("completeness"),
            "groundedness": self._mean("groundedness"),
            "format_compliance": self._mean("format_compliance"),
            "average_latency_ms": (
                round(sum(c.latency_ms for c in self.cases) / len(self.cases))
                if self.cases
                else 0
            ),
            "total_cost": round(sum(c.estimated_cost for c in self.cases), 5),
            "average_cost": (
                round(sum(c.estimated_cost for c in self.cases) / len(self.cases), 5)
                if self.cases
                else 0.0
            ),
            "governance_cases": len(blocking_cases),
            "governance_blocked": sum(1 for c in blocking_cases if c.blocked),
        }


async def run_case(
    db: AsyncSession,
    *,
    user: User,
    workflow: Workflow,
    version: WorkflowVersion,
    case: dict,
) -> CaseResult:
    provider = get_provider()
    result = CaseResult(
        case_id=case["case_id"],
        case_type=case["case_type"],
        expected_behaviour=case.get("expected_behaviour", "answer"),
    )

    decision = await evaluate_request(
        db,
        user=user,
        workflow=workflow,
        inputs=case["inputs"],
        provider=provider,
        acknowledge_warnings=True,
        record_violations=False,
    )
    if decision.blocked:
        result.blocked = True
        result.reasoning = decision.reason
        result.passed_expectation = result.expected_behaviour == "block"
        return result

    if result.expected_behaviour == "block":
        # Governance let through something the case says should be stopped.
        result.passed_expectation = False

    rendered = render_prompt(version.prompt_template, case["inputs"])
    try:
        response = await provider.generate(
            GenerationRequest(
                system_prompt=version.system_prompt,
                user_prompt=rendered,
                model=version.model,
                temperature=version.temperature,
                json_schema=(version.evaluation_rubric or {}).get("output_schema"),
                metadata={"workflow_slug": workflow.slug, "benchmark": True},
            )
        )
    except Exception as exc:  # noqa: BLE001 - reported per case, never fatal
        result.error = str(exc)[:500]
        result.passed_expectation = False
        return result

    result.latency_ms = response.latency_ms
    result.estimated_cost = estimate_cost(
        response.model, response.input_tokens, response.output_tokens
    )

    rubric = dict(version.evaluation_rubric or {})
    # Case-level expectations become extra judge criteria for this run only.
    if case.get("expected_requirements"):
        rubric["criteria"] = list(rubric.get("criteria", [])) + case["expected_requirements"]

    outcome = await evaluate(
        provider,
        task=f"{workflow.name}: {workflow.description}",
        inputs=case["inputs"],
        output=response.text,
        rubric=rubric,
    )
    result.overall_score = outcome.overall_score
    result.relevance = outcome.relevance
    result.completeness = outcome.completeness
    result.groundedness = outcome.groundedness
    result.format_compliance = outcome.format_compliance
    result.deterministic = [check.as_dict() for check in outcome.deterministic_checks]
    result.reasoning = outcome.evaluation_reasoning
    return result


async def benchmark_version(
    db: AsyncSession,
    *,
    user: User,
    workflow: Workflow,
    version: WorkflowVersion,
    cases: list[dict] | None = None,
) -> VersionBenchmark:
    cases = cases if cases is not None else load_cases(workflow.slug)
    benchmark = VersionBenchmark(version=version.version, model=version.model)
    for case in cases:
        benchmark.cases.append(
            await run_case(db, user=user, workflow=workflow, version=version, case=case)
        )
    return benchmark


def compare(a: VersionBenchmark, b: VersionBenchmark) -> str:
    """One-paragraph, quantity-first comparison. No verdict the numbers do not support."""
    left, right = a.summary(), b.summary()
    if left["average_quality"] is None or right["average_quality"] is None:
        return "Not enough scored cases to compare these versions."

    quality_delta = round(right["average_quality"] - left["average_quality"], 1)
    cost_delta = round(right["average_cost"] - left["average_cost"], 5)
    latency_delta = right["average_latency_ms"] - left["average_latency_ms"]

    direction = "improves" if quality_delta > 0 else "reduces" if quality_delta < 0 else "matches"
    parts = [
        f"Across {right['cases_scored']} shared cases, v{right['version']} {direction} "
        f"average quality by {abs(quality_delta)} points "
        f"({left['average_quality']} -> {right['average_quality']})."
    ]
    if left["groundedness"] is not None and right["groundedness"] is not None:
        parts.append(
            f"Groundedness moves {round(right['groundedness'] - left['groundedness'], 1):+} "
            f"({left['groundedness']} -> {right['groundedness']})."
        )
    parts.append(
        f"Average cost per case changes by ${cost_delta:+.5f} and latency by {latency_delta:+}ms."
    )
    if right["governance_cases"]:
        parts.append(
            f"Governance stopped {right['governance_blocked']} of {right['governance_cases']} "
            "cases that were expected to be blocked."
        )
    parts.append(
        "These are benchmark cases, not production traffic: treat the delta as a "
        "directional signal and confirm it against human approval once the version ships."
    )
    return " ".join(parts)
