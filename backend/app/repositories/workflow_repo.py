"""Data access for workflows, kept out of the route layer."""

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import ExecutionStatus
from app.models.execution import EvaluationResult, Execution, HumanFeedback
from app.models.workflow import Workflow, WorkflowVersion


async def list_workflows(
    db: AsyncSession,
    *,
    department: str | None = None,
    target_role: str | None = None,
    task_type: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
) -> list[Workflow]:
    stmt = select(Workflow)
    if department:
        stmt = stmt.where(Workflow.department == department)
    if target_role:
        stmt = stmt.where(Workflow.target_role == target_role)
    if task_type:
        stmt = stmt.where(Workflow.task_type == task_type)
    if risk_level:
        stmt = stmt.where(Workflow.risk_level == risk_level)
    if status:
        stmt = stmt.where(Workflow.status == status)
    stmt = stmt.order_by(Workflow.department, Workflow.name)
    return list((await db.execute(stmt)).scalars().all())


async def get_workflow(db: AsyncSession, workflow_id: str) -> Workflow | None:
    stmt = (
        select(Workflow)
        .options(selectinload(Workflow.versions))
        .where(Workflow.id == workflow_id)
    )
    return (await db.execute(stmt)).scalars().first()


async def get_workflow_by_slug(db: AsyncSession, slug: str) -> Workflow | None:
    stmt = select(Workflow).options(selectinload(Workflow.versions)).where(Workflow.slug == slug)
    return (await db.execute(stmt)).scalars().first()


async def workflow_stats(db: AsyncSession) -> dict[str, dict]:
    """Execution count, mean evaluation score and approval rate per workflow."""
    usage_stmt = (
        select(
            Execution.workflow_id,
            func.count(Execution.id).label("executions"),
            func.avg(EvaluationResult.overall_score).label("quality"),
        )
        .outerjoin(EvaluationResult, EvaluationResult.execution_id == Execution.id)
        .where(Execution.status == ExecutionStatus.COMPLETED)
        .group_by(Execution.workflow_id)
    )
    stats: dict[str, dict] = {}
    for row in (await db.execute(usage_stmt)).all():
        stats[row.workflow_id] = {
            "executions": int(row.executions),
            "average_quality": round(float(row.quality), 1) if row.quality is not None else None,
            "human_approval_rate": None,
        }

    approval_stmt = (
        select(
            Execution.workflow_id,
            func.count(HumanFeedback.id).label("reviewed"),
            func.coalesce(
                func.sum(case((HumanFeedback.approved.is_(True), 1), else_=0)), 0
            ).label("approved"),
        )
        .select_from(HumanFeedback)
        .join(Execution, HumanFeedback.execution_id == Execution.id)
        .group_by(Execution.workflow_id)
    )
    for row in (await db.execute(approval_stmt)).all():
        entry = stats.setdefault(
            row.workflow_id,
            {"executions": 0, "average_quality": None, "human_approval_rate": None},
        )
        reviewed = int(row.reviewed or 0)
        approved = int(row.approved or 0)
        entry["human_approval_rate"] = round(100.0 * approved / reviewed, 1) if reviewed else None

    return stats


async def next_version_number(db: AsyncSession, workflow_id: str) -> int:
    current = (
        await db.execute(
            select(func.max(WorkflowVersion.version)).where(
                WorkflowVersion.workflow_id == workflow_id
            )
        )
    ).scalar()
    return int(current or 0) + 1


async def deactivate_versions(db: AsyncSession, workflow_id: str) -> None:
    versions = (
        (
            await db.execute(
                select(WorkflowVersion).where(WorkflowVersion.workflow_id == workflow_id)
            )
        )
        .scalars()
        .all()
    )
    for version in versions:
        version.is_active = False
