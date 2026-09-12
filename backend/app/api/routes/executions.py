from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.enums import ExecutionStatus, FeedbackDecision
from app.models.execution import EvaluationResult, HumanFeedback
from app.models.user import User
from app.repositories import execution_repo, workflow_repo
from app.schemas.execution import (
    EvaluationOut,
    ExecutionCreate,
    ExecutionOut,
    FeedbackCreate,
    FeedbackOut,
    GovernanceOut,
)
from app.services.ai import get_provider
from app.services.evaluation import evaluate
from app.services.execution_service import ExecutionBlocked, get_active_version, run_workflow

router = APIRouter(prefix="/executions", tags=["executions"])


async def _serialise(db: AsyncSession, execution, governance: dict | None = None) -> ExecutionOut:
    workflow_name, version, user_name = await execution_repo.execution_context(db, execution)
    payload = ExecutionOut.model_validate(execution)
    payload.workflow_name = workflow_name
    payload.workflow_version = version
    payload.user_name = user_name
    if execution.evaluation is not None:
        payload.evaluation = EvaluationOut.model_validate(execution.evaluation)
    if execution.feedback is not None:
        payload.feedback = FeedbackOut.model_validate(execution.feedback)
    if governance is not None:
        payload.governance = GovernanceOut(**governance)
    return payload


@router.post("", response_model=ExecutionOut, status_code=status.HTTP_201_CREATED)
async def create_execution(
    payload: ExecutionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExecutionOut:
    """Run a workflow. Governance runs first; a blocked request never reaches
    the AI provider and its input is not persisted."""
    workflow = await workflow_repo.get_workflow(db, payload.workflow_id)
    if workflow is None:
        workflow = await workflow_repo.get_workflow_by_slug(db, payload.workflow_id)
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")

    try:
        execution, decision = await run_workflow(
            db,
            user=user,
            workflow=workflow,
            inputs=payload.inputs,
            acknowledge_warnings=payload.acknowledge_warnings,
        )
    except ExecutionBlocked as blocked:
        # Non-blocking warnings the user has not acknowledged yet.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": blocked.decision.reason, **blocked.decision.as_dict()},
        ) from blocked

    await db.refresh(execution, attribute_names=["evaluation", "feedback"])
    return await _serialise(db, execution, decision.as_dict())


@router.get("", response_model=list[ExecutionOut])
async def list_executions(
    workflow_id: str | None = None,
    user_id: str | None = None,
    limit: int = Query(default=25, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ExecutionOut]:
    executions = await execution_repo.list_executions(
        db, viewer=user, workflow_id=workflow_id, user_id=user_id, limit=limit, offset=offset
    )
    return [await _serialise(db, execution) for execution in executions]


async def _load_visible(db: AsyncSession, execution_id: str, viewer: User):
    execution = await execution_repo.get_execution(db, execution_id)
    if execution is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execution not found")
    owner_department = (
        await db.execute(select(User.department_id).where(User.id == execution.user_id))
    ).scalar()
    if not execution_repo.can_view(viewer, execution, owner_department):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted to view this execution")
    return execution


@router.get("/{execution_id}", response_model=ExecutionOut)
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExecutionOut:
    execution = await _load_visible(db, execution_id, user)
    return await _serialise(db, execution)


@router.post("/{execution_id}/evaluate", response_model=EvaluationOut)
async def evaluate_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvaluationOut:
    """Re-run automated evaluation for an execution (e.g. after a rubric change)."""
    execution = await _load_visible(db, execution_id, user)
    if execution.status != ExecutionStatus.COMPLETED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only completed executions can be scored")

    workflow = await workflow_repo.get_workflow(db, execution.workflow_id)
    version = await get_active_version(db, workflow)
    outcome = await evaluate(
        get_provider(),
        task=f"{workflow.name}: {workflow.description}",
        inputs=execution.inputs,
        output=execution.output,
        rubric=version.evaluation_rubric or {},
    )

    result = execution.evaluation or EvaluationResult(execution_id=execution.id)
    result.relevance = outcome.relevance
    result.completeness = outcome.completeness
    result.groundedness = outcome.groundedness
    result.clarity = outcome.clarity
    result.format_compliance = outcome.format_compliance
    result.safety_passed = outcome.safety_passed
    result.overall_score = outcome.overall_score
    result.deterministic_checks = [check.as_dict() for check in outcome.deterministic_checks]
    result.evaluation_model = outcome.evaluation_model
    result.evaluation_reasoning = outcome.evaluation_reasoning
    result.rubric_used = outcome.rubric_used
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return EvaluationOut.model_validate(result)


@router.get("/{execution_id}/evaluation", response_model=EvaluationOut)
async def get_evaluation(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvaluationOut:
    execution = await _load_visible(db, execution_id, user)
    if execution.evaluation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No evaluation recorded")
    return EvaluationOut.model_validate(execution.evaluation)


@router.post(
    "/{execution_id}/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED
)
async def submit_feedback(
    execution_id: str,
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackOut:
    """Level 3 evaluation. Human judgement is stored separately from the model
    judge so the two can be compared rather than conflated."""
    execution = await _load_visible(db, execution_id, user)

    feedback = execution.feedback or HumanFeedback(execution_id=execution.id, user_id=user.id)
    feedback.decision = payload.decision
    feedback.approved = payload.decision == FeedbackDecision.APPROVED
    feedback.edited = payload.decision == FeedbackDecision.NEEDS_EDITING
    feedback.thumbs_up = (
        payload.thumbs_up
        if payload.thumbs_up is not None
        else payload.decision == FeedbackDecision.APPROVED
    )
    feedback.rating = payload.rating
    feedback.comment = payload.comment
    feedback.user_id = user.id
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return FeedbackOut.model_validate(feedback)
