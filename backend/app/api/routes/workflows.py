from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.enums import RiskLevel, WorkflowStatus
from app.models.user import User
from app.models.workflow import Workflow, WorkflowVersion
from app.repositories import workflow_repo
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowDetail,
    WorkflowOut,
    WorkflowStats,
    WorkflowUpdate,
    WorkflowVersionCreate,
    WorkflowVersionOut,
)
from app.services.evaluation.scoring import DEFAULT_WEIGHTS

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _serialise(workflow: Workflow, stats: dict | None) -> WorkflowOut:
    payload = WorkflowOut.model_validate(workflow)
    payload.stats = WorkflowStats(**(stats or {}))
    return payload


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    department: str | None = None,
    target_role: str | None = Query(default=None, alias="role"),
    task_type: str | None = None,
    risk_level: RiskLevel | None = None,
    workflow_status: WorkflowStatus | None = Query(default=None, alias="status"),
    recommended: bool = Query(default=False, description="Limit to the caller's job role"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WorkflowOut]:
    if recommended and not target_role:
        target_role = user.job_role

    workflows = await workflow_repo.list_workflows(
        db,
        department=department,
        target_role=target_role,
        task_type=task_type,
        risk_level=risk_level.value if risk_level else None,
        status=workflow_status.value if workflow_status else None,
    )
    stats = await workflow_repo.workflow_stats(db)
    return [_serialise(workflow, stats.get(workflow.id)) for workflow in workflows]


@router.get("/{workflow_id}", response_model=WorkflowDetail)
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkflowDetail:
    workflow = await workflow_repo.get_workflow(db, workflow_id)
    if workflow is None:
        workflow = await workflow_repo.get_workflow_by_slug(db, workflow_id)
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")

    stats = await workflow_repo.workflow_stats(db)
    detail = WorkflowDetail.model_validate(workflow)
    detail.stats = WorkflowStats(**(stats.get(workflow.id) or {}))
    active = next((v for v in workflow.versions if v.is_active), None)
    if active is None and workflow.versions:
        active = sorted(workflow.versions, key=lambda v: v.version)[-1]
    if active is not None:
        detail.active_version = WorkflowVersionOut.model_validate(active)
    return detail


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionOut])
async def list_versions(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WorkflowVersionOut]:
    workflow = await workflow_repo.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return [WorkflowVersionOut.model_validate(v) for v in workflow.versions]


@router.post("", response_model=WorkflowDetail, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> WorkflowDetail:
    if await workflow_repo.get_workflow_by_slug(db, payload.slug):
        raise HTTPException(status.HTTP_409_CONFLICT, "A workflow with that slug already exists")

    workflow = Workflow(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        department=payload.department,
        target_role=payload.target_role,
        task_type=payload.task_type,
        risk_level=payload.risk_level,
        requires_human_review=payload.requires_human_review,
        allowed_data_classification=payload.allowed_data_classification,
        expected_output_format=payload.expected_output_format,
        estimated_manual_minutes=payload.estimated_manual_minutes,
        estimated_assisted_minutes=payload.estimated_assisted_minutes,
        input_schema=[field.model_dump() for field in payload.input_schema],
        guidance=payload.guidance.model_dump(),
        current_version=1,
    )
    db.add(workflow)
    await db.flush()

    version = WorkflowVersion(
        workflow_id=workflow.id,
        version=1,
        system_prompt=payload.system_prompt,
        prompt_template=payload.prompt_template,
        model=payload.model or "gpt-4.1-mini",
        temperature=payload.temperature,
        evaluation_rubric=payload.evaluation_rubric or {"weights": DEFAULT_WEIGHTS},
        changelog="Initial version.",
        created_by=admin.id,
        is_active=True,
    )
    db.add(version)
    await db.commit()

    return await get_workflow(workflow.id, db=db, user=admin)


@router.put("/{workflow_id}", response_model=WorkflowDetail)
async def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> WorkflowDetail:
    workflow = await workflow_repo.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(workflow, field, value)
    await db.commit()
    return await get_workflow(workflow_id, db=db, user=admin)


@router.post(
    "/{workflow_id}/versions",
    response_model=WorkflowVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    workflow_id: str,
    payload: WorkflowVersionCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> WorkflowVersionOut:
    """Add a new prompt version. Existing versions are never overwritten, so
    evaluation history stays attributable to the prompt that produced it."""
    workflow = await workflow_repo.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")

    previous = sorted(workflow.versions, key=lambda v: v.version)[-1] if workflow.versions else None
    number = await workflow_repo.next_version_number(db, workflow.id)

    if payload.activate:
        await workflow_repo.deactivate_versions(db, workflow.id)

    version = WorkflowVersion(
        workflow_id=workflow.id,
        version=number,
        system_prompt=payload.system_prompt,
        prompt_template=payload.prompt_template,
        model=payload.model or (previous.model if previous else "gpt-4.1-mini"),
        provider=payload.provider if payload.provider is not None
        else (previous.provider if previous else None),
        temperature=payload.temperature,
        evaluation_rubric=payload.evaluation_rubric
        or (previous.evaluation_rubric if previous else {"weights": DEFAULT_WEIGHTS}),
        changelog=payload.changelog,
        created_by=admin.id,
        is_active=payload.activate,
    )
    db.add(version)
    if payload.activate:
        workflow.current_version = number
    await db.commit()
    await db.refresh(version)
    return WorkflowVersionOut.model_validate(version)
