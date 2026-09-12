from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_manager
from app.core.database import get_db
from app.models.governance import GovernancePolicy, PolicyViolation
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.analytics import AdoptionSummary, QualitySummary, WorkflowQuality
from app.services import analytics

router = APIRouter(prefix="/admin", tags=["admin"])


class PolicyOut(BaseModel):
    id: str
    key: str
    name: str
    description: str
    risk_level: str
    enabled: bool
    blocking: bool
    config: dict

    model_config = {"from_attributes": True}


class PolicyUpdate(BaseModel):
    enabled: bool | None = None
    blocking: bool | None = None
    risk_level: str | None = None
    config: dict | None = None


class ViolationOut(BaseModel):
    id: str
    policy_key: str
    violation_type: str
    severity: str
    blocked: bool
    details: dict
    workflow_name: str = ""
    user_name: str = ""
    created_at: str


class AdminOverview(BaseModel):
    adoption: AdoptionSummary
    quality: QualitySummary
    top_workflows: list[WorkflowQuality]
    needs_attention: list[WorkflowQuality]
    blocked_requests: int


@router.get("/overview", response_model=AdminOverview)
async def overview(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AdminOverview:
    adoption = AdoptionSummary(**await analytics.adoption_summary(db, days))
    quality = QualitySummary(**await analytics.quality_summary(db, days))
    workflow_rows = [WorkflowQuality(**row) for row in await analytics.workflow_quality(db, days)]

    blocked = (
        await db.execute(
            select(func.count(PolicyViolation.id)).where(PolicyViolation.blocked.is_(True))
        )
    ).scalar_one()

    top = sorted(workflow_rows, key=lambda row: row.executions, reverse=True)[:5]
    attention = [row for row in workflow_rows if row.needs_attention][:5]
    return AdminOverview(
        adoption=adoption,
        quality=quality,
        top_workflows=top,
        needs_attention=attention,
        blocked_requests=int(blocked),
    )


@router.get("/governance", response_model=list[PolicyOut])
async def list_policies(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[PolicyOut]:
    rows = (await db.execute(select(GovernancePolicy).order_by(GovernancePolicy.name))).scalars()
    return [PolicyOut.model_validate(policy) for policy in rows.all()]


@router.put("/governance/{policy_id}", response_model=PolicyOut)
async def update_policy(
    policy_id: str,
    payload: PolicyUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> PolicyOut:
    policy = (
        await db.execute(select(GovernancePolicy).where(GovernancePolicy.id == policy_id))
    ).scalars().first()
    if policy is None:
        policy = (
            await db.execute(select(GovernancePolicy).where(GovernancePolicy.key == policy_id))
        ).scalars().first()
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    await db.commit()
    await db.refresh(policy)
    return PolicyOut.model_validate(policy)


@router.get("/violations", response_model=list[ViolationOut])
async def list_violations(
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    viewer: User = Depends(require_manager),
) -> list[ViolationOut]:
    """Audit log. Records categories and counts, never the detected value."""
    stmt = (
        select(PolicyViolation, Workflow.name, User.name)
        .outerjoin(Workflow, PolicyViolation.workflow_id == Workflow.id)
        .outerjoin(User, PolicyViolation.user_id == User.id)
        .order_by(desc(PolicyViolation.created_at))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        ViolationOut(
            id=violation.id,
            policy_key=violation.policy_key,
            violation_type=violation.violation_type,
            severity=violation.severity,
            blocked=violation.blocked,
            details=violation.details,
            workflow_name=workflow_name or "",
            user_name=user_name or "",
            created_at=violation.created_at.isoformat(),
        )
        for violation, workflow_name, user_name in rows
    ]
