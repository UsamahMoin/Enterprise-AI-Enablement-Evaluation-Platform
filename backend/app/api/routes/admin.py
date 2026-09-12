from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_manager
from app.core.config import settings
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


class ProviderOut(BaseModel):
    name: str
    configured: bool = True
    supports_moderation: bool = False
    max_data_classification: str = ""
    keeps_data_in_house: bool = False
    description: str = ""
    error: str = ""
    is_default: bool = False
    is_judge: bool = False
    reachable: bool | None = None
    models: list[str] = []


class ProviderSettingsOut(BaseModel):
    generation_provider: str
    evaluation_provider: str
    moderation_provider: str
    moderation_fail_closed: bool
    providers: list[ProviderOut]


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


@router.get("/providers", response_model=ProviderSettingsOut)
async def list_providers(viewer: User = Depends(require_manager)) -> ProviderSettingsOut:
    """Provider capabilities, so governance decisions are explainable.

    Providers are not interchangeable in the ways governance cares about: one
    keeps data in-house but cannot moderate, another moderates well but is an
    egress of data. This is the screen that says which is which.
    """
    from app.services.ai import available_providers
    from app.services.ai.local_provider import LocalProvider

    rows: list[ProviderOut] = []
    for summary in available_providers():
        row = ProviderOut(
            name=summary["name"],
            configured="error" not in summary,
            supports_moderation=summary.get("supports_moderation", False),
            max_data_classification=summary.get("max_data_classification", ""),
            keeps_data_in_house=summary.get("keeps_data_in_house", False),
            description=summary.get("description", ""),
            error=summary.get("error", ""),
            is_default=summary["name"] == settings.ai_provider,
            is_judge=summary["name"] == settings.judge_provider,
        )
        if row.name == "local" and row.configured:
            health = await LocalProvider().health()
            row.reachable = health["reachable"]
            row.models = health.get("models", [])
            if not health["reachable"]:
                row.error = health.get("error", "")
        rows.append(row)

    return ProviderSettingsOut(
        generation_provider=settings.ai_provider,
        evaluation_provider=settings.judge_provider,
        moderation_provider=settings.moderation_provider or "(generation provider)",
        moderation_fail_closed=settings.moderation_fail_closed,
        providers=rows,
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
