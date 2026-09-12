"""Data access for executions and their evaluation/feedback children."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import SystemRole
from app.models.execution import Execution
from app.models.user import User
from app.models.workflow import Workflow, WorkflowVersion


def _base_stmt():
    return select(Execution).options(
        selectinload(Execution.evaluation), selectinload(Execution.feedback)
    )


async def get_execution(db: AsyncSession, execution_id: str) -> Execution | None:
    return (await db.execute(_base_stmt().where(Execution.id == execution_id))).scalars().first()


async def list_executions(
    db: AsyncSession,
    *,
    viewer: User,
    workflow_id: str | None = None,
    user_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Execution]:
    """Scope results to what the viewer is entitled to see.

    Employees see only their own runs. Managers see their department's runs
    (aggregates, not another employee's raw prompts, are the intended use).
    Admins see everything.
    """
    stmt = _base_stmt()

    if viewer.system_role == SystemRole.EMPLOYEE:
        stmt = stmt.where(Execution.user_id == viewer.id)
    elif viewer.system_role == SystemRole.MANAGER:
        stmt = stmt.join(User, Execution.user_id == User.id).where(
            User.department_id == viewer.department_id
        )
    if workflow_id:
        stmt = stmt.where(Execution.workflow_id == workflow_id)
    if user_id:
        stmt = stmt.where(Execution.user_id == user_id)

    stmt = stmt.order_by(Execution.created_at.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


async def execution_context(db: AsyncSession, execution: Execution) -> tuple[str, int, str]:
    """Return (workflow_name, version_number, user_name) for serialisation."""
    workflow_name = (
        await db.execute(select(Workflow.name).where(Workflow.id == execution.workflow_id))
    ).scalar() or ""
    version = (
        await db.execute(
            select(WorkflowVersion.version).where(
                WorkflowVersion.id == execution.workflow_version_id
            )
        )
    ).scalar() or 0
    user_name = (
        await db.execute(select(User.name).where(User.id == execution.user_id))
    ).scalar() or ""
    return workflow_name, int(version), user_name


def can_view(viewer: User, execution: Execution, owner_department_id: str | None) -> bool:
    if viewer.system_role == SystemRole.ADMIN:
        return True
    if execution.user_id == viewer.id:
        return True
    if viewer.system_role == SystemRole.MANAGER:
        return owner_department_id == viewer.department_id
    return False
