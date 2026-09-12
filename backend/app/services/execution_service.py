"""Workflow execution: governance -> generation -> evaluation -> persistence."""

import time
from string import Template

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ExecutionStatus
from app.models.execution import EvaluationResult, Execution
from app.models.user import User
from app.models.workflow import Workflow, WorkflowVersion
from app.services.ai import GenerationRequest, estimate_cost, get_provider
from app.services.evaluation import evaluate
from app.services.governance import GovernanceDecision, evaluate_request


class ExecutionBlocked(Exception):
    """Raised when governance stops a request before it reaches a provider."""

    def __init__(self, decision: GovernanceDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


def render_prompt(template: str, inputs: dict) -> str:
    """Fill a prompt template.

    `string.Template` is used rather than str.format so that braces in user
    content (JSON, code) cannot break rendering or inject placeholders.
    """
    safe_inputs = {key: ("" if value is None else str(value)) for key, value in (inputs or {}).items()}
    return Template(template).safe_substitute(safe_inputs)


async def get_active_version(db: AsyncSession, workflow: Workflow) -> WorkflowVersion:
    stmt = (
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow.id, WorkflowVersion.is_active.is_(True))
        .order_by(WorkflowVersion.version.desc())
    )
    version = (await db.execute(stmt)).scalars().first()
    if version is None:
        stmt = (
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow.id)
            .order_by(WorkflowVersion.version.desc())
        )
        version = (await db.execute(stmt)).scalars().first()
    if version is None:
        raise ValueError(f"Workflow {workflow.slug} has no versions")
    return version


async def run_workflow(
    db: AsyncSession,
    *,
    user: User,
    workflow: Workflow,
    inputs: dict,
    acknowledge_warnings: bool = False,
    version: WorkflowVersion | None = None,
    run_evaluation: bool = True,
) -> tuple[Execution, GovernanceDecision]:
    """Execute one workflow end to end and persist the result."""
    provider = get_provider()
    version = version or await get_active_version(db, workflow)

    # 1. Governance pre-flight -------------------------------------------
    decision = await evaluate_request(
        db,
        user=user,
        workflow=workflow,
        inputs=inputs,
        provider=provider,
        acknowledge_warnings=acknowledge_warnings,
    )
    if not decision.allowed:
        if decision.blocked:
            execution = Execution(
                user_id=user.id,
                workflow_id=workflow.id,
                workflow_version_id=version.id,
                inputs={},  # blocked input is never persisted
                status=ExecutionStatus.BLOCKED,
                blocked_reason=decision.reason,
                provider=provider.name,
                model=version.model,
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)
            return execution, decision
        raise ExecutionBlocked(decision)

    # 2. Generation -------------------------------------------------------
    rendered = render_prompt(version.prompt_template, inputs)
    started = time.perf_counter()
    execution = Execution(
        user_id=user.id,
        workflow_id=workflow.id,
        workflow_version_id=version.id,
        inputs=inputs,
        rendered_prompt=rendered,
        model=version.model,
        provider=provider.name,
        status=ExecutionStatus.PENDING,
    )

    try:
        response = await provider.generate(
            GenerationRequest(
                system_prompt=version.system_prompt,
                user_prompt=rendered,
                model=version.model,
                temperature=version.temperature,
                json_schema=(version.evaluation_rubric or {}).get("output_schema"),
                metadata={"workflow_slug": workflow.slug, "version": version.version},
            )
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a failed run
        execution.status = ExecutionStatus.FAILED
        execution.error = str(exc)[:1000]
        execution.latency_ms = int((time.perf_counter() - started) * 1000)
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        return execution, decision

    execution.output = response.text
    execution.input_tokens = response.input_tokens
    execution.output_tokens = response.output_tokens
    execution.latency_ms = response.latency_ms
    execution.estimated_cost = estimate_cost(
        response.model, response.input_tokens, response.output_tokens
    )
    execution.status = ExecutionStatus.COMPLETED
    db.add(execution)
    await db.flush()

    # 3. Evaluation -------------------------------------------------------
    if run_evaluation:
        outcome = await evaluate(
            provider,
            task=f"{workflow.name}: {workflow.description}",
            inputs=inputs,
            output=response.text,
            rubric=version.evaluation_rubric or {},
        )
        db.add(
            EvaluationResult(
                execution_id=execution.id,
                relevance=outcome.relevance,
                completeness=outcome.completeness,
                groundedness=outcome.groundedness,
                clarity=outcome.clarity,
                format_compliance=outcome.format_compliance,
                safety_passed=outcome.safety_passed,
                overall_score=outcome.overall_score,
                deterministic_checks=[check.as_dict() for check in outcome.deterministic_checks],
                evaluation_model=outcome.evaluation_model,
                evaluation_reasoning=outcome.evaluation_reasoning,
                rubric_used=outcome.rubric_used,
            )
        )

    await db.commit()
    await db.refresh(execution)
    return execution, decision
