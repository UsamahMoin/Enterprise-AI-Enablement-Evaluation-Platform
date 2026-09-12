from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_manager
from app.core.database import get_db
from app.core.enums import SystemRole
from app.models.user import User
from app.repositories import workflow_repo
from app.schemas.analytics import (
    AdoptionSummary,
    CostSummary,
    DepartmentAdoption,
    QualitySummary,
    UserDashboard,
    VersionComparison,
    WorkflowQuality,
)
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])

WindowDays = Query(default=30, ge=1, le=365, description="Rolling window in days")


@router.get("/me", response_model=UserDashboard)
async def my_dashboard(
    days: int = WindowDays,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserDashboard:
    from app.services.training_service import training_progress

    data = await analytics.user_dashboard(db, user, days)
    completed, total = await training_progress(db, user)
    data["training_completed"] = completed
    data["training_total"] = total
    return UserDashboard(**data)


@router.get("/adoption", response_model=AdoptionSummary)
async def adoption(
    days: int = WindowDays,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_manager),
) -> AdoptionSummary:
    return AdoptionSummary(**await analytics.adoption_summary(db, days))


@router.get("/departments", response_model=list[DepartmentAdoption])
async def departments(
    days: int = WindowDays,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_manager),
) -> list[DepartmentAdoption]:
    rows = await analytics.department_adoption(db, days)
    # A manager sees their own department only; aggregate rows, never another
    # employee's raw prompts.
    if user.system_role == SystemRole.MANAGER and user.department is not None:
        rows = [row for row in rows if row["department"] == user.department.name]
    return [DepartmentAdoption(**row) for row in rows]


@router.get("/quality", response_model=QualitySummary)
async def quality(
    days: int = WindowDays,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_manager),
) -> QualitySummary:
    return QualitySummary(**await analytics.quality_summary(db, days))


@router.get("/workflows", response_model=list[WorkflowQuality])
async def workflows(
    days: int = WindowDays,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_manager),
) -> list[WorkflowQuality]:
    rows = await analytics.workflow_quality(db, days)
    return [WorkflowQuality(**row) for row in rows]


@router.get("/cost", response_model=CostSummary)
async def cost(
    days: int = WindowDays,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_manager),
) -> CostSummary:
    return CostSummary(**await analytics.cost_summary(db, days))


@router.get("/workflows/{workflow_id}/versions", response_model=VersionComparison)
async def compare_versions(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_manager),
) -> VersionComparison:
    """Prompt v1 vs v2 vs v3 on the same evaluation dimensions."""
    workflow = await workflow_repo.get_workflow(db, workflow_id)
    if workflow is None:
        workflow = await workflow_repo.get_workflow_by_slug(db, workflow_id)
    if workflow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workflow not found")
    return VersionComparison(**await analytics.version_comparison(db, workflow))
