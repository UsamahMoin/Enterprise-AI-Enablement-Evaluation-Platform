"""Adoption, quality and cost analytics.

Two deliberate choices show up throughout this module:

1. Time saved is always called *estimated*. It is derived from a per-workflow
   `estimated_manual_minutes` baseline, credited only for approved outputs,
   and never presented as a measured productivity gain.
2. Adoption is split into usage and *effective* usage. Sending prompts is not
   the same as producing work someone accepted.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Float, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ExecutionStatus
from app.models.execution import EvaluationResult, Execution, HumanFeedback
from app.models.organization import Department
from app.models.user import User
from app.models.workflow import Workflow, WorkflowVersion

DEFAULT_WINDOW_DAYS = 30


def window_start(days: int = DEFAULT_WINDOW_DAYS) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)


def _rate(numerator: float, denominator: float) -> float:
    return round(100.0 * numerator / denominator, 1) if denominator else 0.0


def _completed(stmt, since: datetime | None = None):
    stmt = stmt.where(Execution.status == ExecutionStatus.COMPLETED)
    if since is not None:
        stmt = stmt.where(Execution.created_at >= since)
    return stmt


async def adoption_summary(db: AsyncSession, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    since = window_start(days)

    total_employees = (await db.execute(select(func.count(User.id)))).scalar_one()

    licensed_users = (
        await db.execute(_completed(select(func.count(func.distinct(Execution.user_id)))))
    ).scalar_one()

    active_users = (
        await db.execute(_completed(select(func.count(func.distinct(Execution.user_id))), since))
    ).scalar_one()

    effective_users = (
        await db.execute(
            _completed(
                select(func.count(func.distinct(Execution.user_id)))
                .join(HumanFeedback, HumanFeedback.execution_id == Execution.id)
                .where(HumanFeedback.approved.is_(True)),
                since,
            )
        )
    ).scalar_one()

    totals = (
        await db.execute(
            _completed(
                select(
                    func.count(Execution.id),
                    func.coalesce(func.sum(Execution.estimated_cost), 0.0),
                ),
                since,
            )
        )
    ).one()
    executions, spend = int(totals[0]), float(totals[1])

    feedback_totals = (
        await db.execute(
            _completed(
                select(
                    func.count(HumanFeedback.id),
                    func.coalesce(
                        func.sum(case((HumanFeedback.approved.is_(True), 1), else_=0)), 0
                    ),
                ).join(Execution, HumanFeedback.execution_id == Execution.id),
                since,
            )
        )
    ).one()
    reviewed, approved = int(feedback_totals[0]), int(feedback_totals[1])

    minutes_saved = (
        await db.execute(
            _completed(
                select(
                    func.coalesce(
                        func.sum(
                            Workflow.estimated_manual_minutes - Workflow.estimated_assisted_minutes
                        ),
                        0,
                    )
                )
                .select_from(Execution)
                .join(Workflow, Execution.workflow_id == Workflow.id)
                .join(HumanFeedback, HumanFeedback.execution_id == Execution.id)
                .where(HumanFeedback.approved.is_(True)),
                since,
            )
        )
    ).scalar_one()
    minutes_saved = int(minutes_saved or 0)

    return {
        "total_employees": total_employees,
        "licensed_users": licensed_users,
        "active_users": active_users,
        "effective_users": effective_users,
        "adoption_rate": _rate(active_users, total_employees),
        "effective_adoption_rate": _rate(effective_users, active_users),
        "executions": executions,
        "approval_rate": _rate(approved, reviewed),
        "estimated_minutes_saved": minutes_saved,
        "estimated_hours_saved": round(minutes_saved / 60, 1),
        "estimated_spend": round(spend, 2),
        "cost_per_execution": round(spend / executions, 4) if executions else 0.0,
        "cost_per_approved_output": round(spend / approved, 4) if approved else 0.0,
    }


async def department_adoption(db: AsyncSession, days: int = DEFAULT_WINDOW_DAYS) -> list[dict]:
    since = window_start(days)

    headcounts = {
        row.name: (row.id, row.headcount)
        for row in (await db.execute(select(Department))).scalars().all()
    }
    member_counts = dict(
        (
            await db.execute(
                select(User.department_id, func.count(User.id)).group_by(User.department_id)
            )
        ).all()
    )

    stmt = _completed(
        select(
            Department.name.label("department"),
            func.count(func.distinct(Execution.user_id)).label("active_users"),
            func.count(Execution.id).label("executions"),
            func.avg(EvaluationResult.overall_score).label("quality"),
            func.coalesce(func.sum(Execution.estimated_cost), 0.0).label("spend"),
        )
        .select_from(Execution)
        .join(User, Execution.user_id == User.id)
        .join(Department, User.department_id == Department.id)
        .outerjoin(EvaluationResult, EvaluationResult.execution_id == Execution.id)
        .group_by(Department.name),
        since,
    )
    usage = {row.department: row for row in (await db.execute(stmt)).all()}

    approvals_stmt = _completed(
        select(
            Department.name.label("department"),
            func.count(HumanFeedback.id).label("reviewed"),
            func.coalesce(
                func.sum(case((HumanFeedback.approved.is_(True), 1), else_=0)), 0
            ).label("approved"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            HumanFeedback.approved.is_(True),
                            Workflow.estimated_manual_minutes - Workflow.estimated_assisted_minutes,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("minutes_saved"),
        )
        .select_from(HumanFeedback)
        .join(Execution, HumanFeedback.execution_id == Execution.id)
        .join(Workflow, Execution.workflow_id == Workflow.id)
        .join(User, Execution.user_id == User.id)
        .join(Department, User.department_id == Department.id)
        .group_by(Department.name),
        since,
    )
    approvals = {row.department: row for row in (await db.execute(approvals_stmt)).all()}

    results: list[dict] = []
    for name, (dept_id, headcount) in headcounts.items():
        people = member_counts.get(dept_id, 0) or headcount
        row = usage.get(name)
        approval_row = approvals.get(name)
        active = int(row.active_users) if row else 0
        results.append(
            {
                "department": name,
                "headcount": people,
                "active_users": active,
                "adoption_rate": _rate(active, people),
                "executions": int(row.executions) if row else 0,
                "average_quality": round(float(row.quality), 1) if row and row.quality else None,
                "approval_rate": (
                    _rate(int(approval_row.approved), int(approval_row.reviewed))
                    if approval_row and approval_row.reviewed
                    else None
                ),
                "estimated_hours_saved": (
                    round(int(approval_row.minutes_saved) / 60, 1) if approval_row else 0.0
                ),
                "estimated_spend": round(float(row.spend), 2) if row else 0.0,
            }
        )

    results.sort(key=lambda item: item["adoption_rate"], reverse=True)
    return results


async def quality_summary(db: AsyncSession, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    since = window_start(days)

    stmt = _completed(
        select(
            func.avg(EvaluationResult.overall_score),
            func.avg(EvaluationResult.relevance),
            func.avg(EvaluationResult.completeness),
            func.avg(EvaluationResult.groundedness),
            func.avg(EvaluationResult.format_compliance),
            func.avg(EvaluationResult.clarity),
            func.count(EvaluationResult.id),
            func.avg(case((EvaluationResult.safety_passed.is_(True), 1.0), else_=0.0)),
        )
        .select_from(EvaluationResult)
        .join(Execution, EvaluationResult.execution_id == Execution.id),
        since,
    )
    row = (await db.execute(stmt)).one()

    feedback_stmt = _completed(
        select(
            func.count(HumanFeedback.id),
            func.coalesce(func.sum(case((HumanFeedback.approved.is_(True), 1), else_=0)), 0),
        )
        .select_from(HumanFeedback)
        .join(Execution, HumanFeedback.execution_id == Execution.id),
        since,
    )
    reviewed, approved = (await db.execute(feedback_stmt)).one()

    def maybe(value) -> float | None:
        return round(float(value), 1) if value is not None else None

    overall = maybe(row[0])
    approval_rate = _rate(int(approved), int(reviewed)) if reviewed else None

    return {
        "overall_quality": overall,
        "dimensions": {
            "relevance": maybe(row[1]),
            "completeness": maybe(row[2]),
            "groundedness": maybe(row[3]),
            "format_compliance": maybe(row[4]),
            "clarity": maybe(row[5]),
        },
        "human_approval_rate": approval_rate,
        "evaluated_executions": int(row[6] or 0),
        "safety_pass_rate": round(float(row[7]) * 100, 1) if row[7] is not None else None,
        "judge_human_gap": (
            round(overall - approval_rate, 1)
            if overall is not None and approval_rate is not None
            else None
        ),
    }


async def workflow_quality(db: AsyncSession, days: int = DEFAULT_WINDOW_DAYS) -> list[dict]:
    since = window_start(days)

    stmt = _completed(
        select(
            Workflow.id,
            Workflow.name,
            Workflow.department,
            func.count(Execution.id).label("executions"),
            func.avg(EvaluationResult.overall_score).label("quality"),
            func.coalesce(func.sum(Execution.estimated_cost), 0.0).label("spend"),
        )
        .select_from(Execution)
        .join(Workflow, Execution.workflow_id == Workflow.id)
        .outerjoin(EvaluationResult, EvaluationResult.execution_id == Execution.id)
        .group_by(Workflow.id, Workflow.name, Workflow.department),
        since,
    )
    rows = (await db.execute(stmt)).all()

    approval_stmt = _completed(
        select(
            Execution.workflow_id,
            func.count(HumanFeedback.id).label("reviewed"),
            func.coalesce(
                func.sum(case((HumanFeedback.approved.is_(True), 1), else_=0)), 0
            ).label("approved"),
        )
        .select_from(HumanFeedback)
        .join(Execution, HumanFeedback.execution_id == Execution.id)
        .group_by(Execution.workflow_id),
        since,
    )
    approvals = {row.workflow_id: row for row in (await db.execute(approval_stmt)).all()}

    results: list[dict] = []
    for row in rows:
        approval_row = approvals.get(row.id)
        approval_rate = (
            _rate(int(approval_row.approved), int(approval_row.reviewed))
            if approval_row and approval_row.reviewed
            else None
        )
        quality = round(float(row.quality), 1) if row.quality is not None else None

        reason = ""
        if quality is not None and quality < 80:
            reason = f"Average evaluation score {quality} is below the 80 threshold."
        elif approval_rate is not None and approval_rate < 80:
            reason = f"Human approval rate {approval_rate}% is below the 80% threshold."

        results.append(
            {
                "workflow_id": row.id,
                "name": row.name,
                "department": row.department,
                "executions": int(row.executions),
                "average_quality": quality,
                "approval_rate": approval_rate,
                "estimated_spend": round(float(row.spend), 2),
                "needs_attention": bool(reason),
                "attention_reason": reason,
            }
        )

    results.sort(key=lambda item: (item["average_quality"] is None, item["average_quality"] or 0))
    return results


async def cost_summary(db: AsyncSession, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    since = window_start(days)

    totals = (
        await db.execute(
            _completed(
                select(
                    func.coalesce(func.sum(Execution.estimated_cost), 0.0),
                    func.count(Execution.id),
                ),
                since,
            )
        )
    ).one()
    spend, executions = float(totals[0]), int(totals[1])

    approved = (
        await db.execute(
            _completed(
                select(func.count(HumanFeedback.id))
                .select_from(HumanFeedback)
                .join(Execution, HumanFeedback.execution_id == Execution.id)
                .where(HumanFeedback.approved.is_(True)),
                since,
            )
        )
    ).scalar_one()

    async def bucket(label_column, join_clause=None) -> list[dict]:
        stmt = select(
            label_column.label("label"),
            func.coalesce(func.sum(Execution.estimated_cost), 0.0).label("spend"),
            func.count(Execution.id).label("executions"),
        ).select_from(Execution)
        if join_clause is not None:
            stmt = stmt.join(*join_clause)
        stmt = _completed(stmt.group_by(label_column), since)
        rows = (await db.execute(stmt)).all()
        buckets = [
            {
                "label": row.label or "Unassigned",
                "spend": round(float(row.spend), 2),
                "executions": int(row.executions),
                "cost_per_execution": (
                    round(float(row.spend) / int(row.executions), 4) if row.executions else 0.0
                ),
            }
            for row in rows
        ]
        buckets.sort(key=lambda item: item["spend"], reverse=True)
        return buckets

    # Department needs a two-hop join, so it is built explicitly rather than
    # through the single-join `bucket` helper.
    dept_stmt = _completed(
        select(
            Department.name.label("label"),
            func.coalesce(func.sum(Execution.estimated_cost), 0.0).label("spend"),
            func.count(Execution.id).label("executions"),
        )
        .select_from(Execution)
        .join(User, Execution.user_id == User.id)
        .join(Department, User.department_id == Department.id)
        .group_by(Department.name),
        since,
    )
    by_department = [
        {
            "label": row.label,
            "spend": round(float(row.spend), 2),
            "executions": int(row.executions),
            "cost_per_execution": (
                round(float(row.spend) / int(row.executions), 4) if row.executions else 0.0
            ),
        }
        for row in (await db.execute(dept_stmt)).all()
    ]
    by_department.sort(key=lambda item: item["spend"], reverse=True)

    by_workflow = await bucket(Workflow.name, (Workflow, Execution.workflow_id == Workflow.id))
    by_model = await bucket(Execution.model)

    return {
        "total_spend": round(spend, 2),
        "executions": executions,
        "approved_executions": int(approved),
        "cost_per_execution": round(spend / executions, 4) if executions else 0.0,
        "cost_per_approved_output": round(spend / int(approved), 4) if approved else 0.0,
        "by_department": by_department,
        "by_workflow": by_workflow,
        "by_model": by_model,
    }


async def user_dashboard(db: AsyncSession, user: User, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    since = window_start(days)

    totals = (
        await db.execute(
            _completed(
                select(
                    func.count(Execution.id),
                    func.coalesce(func.sum(Execution.estimated_cost), 0.0),
                ).where(Execution.user_id == user.id),
                since,
            )
        )
    ).one()
    executions, spend = int(totals[0]), float(totals[1])

    avg_score = (
        await db.execute(
            _completed(
                select(func.avg(EvaluationResult.overall_score))
                .select_from(EvaluationResult)
                .join(Execution, EvaluationResult.execution_id == Execution.id)
                .where(Execution.user_id == user.id),
                since,
            )
        )
    ).scalar()

    feedback = (
        await db.execute(
            _completed(
                select(
                    func.count(HumanFeedback.id),
                    func.coalesce(
                        func.sum(case((HumanFeedback.approved.is_(True), 1), else_=0)), 0
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    HumanFeedback.approved.is_(True),
                                    Workflow.estimated_manual_minutes
                                    - Workflow.estimated_assisted_minutes,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                )
                .select_from(HumanFeedback)
                .join(Execution, HumanFeedback.execution_id == Execution.id)
                .join(Workflow, Execution.workflow_id == Workflow.id)
                .where(Execution.user_id == user.id),
                since,
            )
        )
    ).one()
    reviewed, approved, minutes = int(feedback[0]), int(feedback[1]), int(feedback[2])

    return {
        "workflows_completed": executions,
        "estimated_hours_saved": round(minutes / 60, 1),
        "average_evaluation_score": round(float(avg_score), 1) if avg_score is not None else None,
        "human_approval_rate": _rate(approved, reviewed) if reviewed else None,
        "estimated_cost": round(spend, 2),
        "training_completed": 0,
        "training_total": 0,
    }


async def version_comparison(db: AsyncSession, workflow: Workflow) -> dict:
    """Per-version quality, so a prompt change can be judged on evidence."""
    stmt = (
        select(
            WorkflowVersion.version,
            WorkflowVersion.changelog,
            func.count(Execution.id).label("executions"),
            func.avg(EvaluationResult.overall_score).label("quality"),
            func.avg(EvaluationResult.relevance).label("relevance"),
            func.avg(EvaluationResult.completeness).label("completeness"),
            func.avg(EvaluationResult.groundedness).label("groundedness"),
            func.avg(EvaluationResult.format_compliance).label("format_compliance"),
            func.avg(Execution.estimated_cost).label("avg_cost"),
            func.avg(func.cast(Execution.latency_ms, Float)).label("avg_latency"),
        )
        .select_from(WorkflowVersion)
        .outerjoin(
            Execution,
            (Execution.workflow_version_id == WorkflowVersion.id)
            & (Execution.status == ExecutionStatus.COMPLETED),
        )
        .outerjoin(EvaluationResult, EvaluationResult.execution_id == Execution.id)
        .where(WorkflowVersion.workflow_id == workflow.id)
        .group_by(WorkflowVersion.version, WorkflowVersion.changelog)
        .order_by(WorkflowVersion.version)
    )
    rows = (await db.execute(stmt)).all()

    approval_stmt = (
        select(
            WorkflowVersion.version,
            func.count(HumanFeedback.id).label("reviewed"),
            func.coalesce(
                func.sum(case((HumanFeedback.approved.is_(True), 1), else_=0)), 0
            ).label("approved"),
        )
        .select_from(HumanFeedback)
        .join(Execution, HumanFeedback.execution_id == Execution.id)
        .join(WorkflowVersion, Execution.workflow_version_id == WorkflowVersion.id)
        .where(WorkflowVersion.workflow_id == workflow.id)
        .group_by(WorkflowVersion.version)
    )
    approvals = {row.version: row for row in (await db.execute(approval_stmt)).all()}

    def maybe(value) -> float | None:
        return round(float(value), 1) if value is not None else None

    versions = []
    for row in rows:
        approval_row = approvals.get(row.version)
        versions.append(
            {
                "version": row.version,
                "executions": int(row.executions or 0),
                "average_quality": maybe(row.quality),
                "relevance": maybe(row.relevance),
                "completeness": maybe(row.completeness),
                "groundedness": maybe(row.groundedness),
                "format_compliance": maybe(row.format_compliance),
                "approval_rate": (
                    _rate(int(approval_row.approved), int(approval_row.reviewed))
                    if approval_row and approval_row.reviewed
                    else None
                ),
                "average_cost": round(float(row.avg_cost or 0), 5),
                "average_latency_ms": round(float(row.avg_latency or 0), 0),
                "changelog": row.changelog or "",
            }
        )

    return {
        "workflow_id": workflow.id,
        "workflow_name": workflow.name,
        "versions": versions,
        "recommendation": build_recommendation(versions),
    }


def build_recommendation(versions: list[dict]) -> str:
    """Plain-language comparison of the two most recent scored versions."""
    scored = [v for v in versions if v["average_quality"] is not None and v["executions"] > 0]
    if len(scored) < 2:
        return "Not enough evaluated executions to compare versions."

    previous, latest = scored[-2], scored[-1]
    quality_delta = round(latest["average_quality"] - previous["average_quality"], 1)
    cost_delta = round(latest["average_cost"] - previous["average_cost"], 5)

    parts = [
        f"v{latest['version']} scores {quality_delta:+} points against v{previous['version']} "
        f"({previous['average_quality']} -> {latest['average_quality']})."
    ]
    if latest["approval_rate"] is not None and previous["approval_rate"] is not None:
        approval_delta = round(latest["approval_rate"] - previous["approval_rate"], 1)
        parts.append(
            f"Human approval moves {approval_delta:+} percentage points "
            f"({previous['approval_rate']}% -> {latest['approval_rate']}%)."
        )
    parts.append(f"Average cost per execution changes by ${cost_delta:+.5f}.")
    return " ".join(parts)
