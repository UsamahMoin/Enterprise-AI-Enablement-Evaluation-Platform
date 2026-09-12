"""Analytics arithmetic, verified against a hand-built dataset."""

from datetime import UTC, datetime, timedelta

from app.core.enums import ExecutionStatus, FeedbackDecision
from app.models.execution import EvaluationResult, Execution, HumanFeedback
from app.services import analytics
from tests.conftest import auth, login


async def _seed(db, users, workflows, *, rows):
    """rows: list of (user, days_ago, score, decision|None, cost)."""
    from sqlalchemy import select

    from app.models.workflow import WorkflowVersion

    version = (
        await db.execute(
            select(WorkflowVersion).where(WorkflowVersion.workflow_id == workflows["unit_tests"].id)
        )
    ).scalars().first()
    now = datetime.now(UTC).replace(tzinfo=None)

    for user, days_ago, score, decision, cost in rows:
        execution = Execution(
            user_id=user.id,
            workflow_id=workflows["unit_tests"].id,
            workflow_version_id=version.id,
            inputs={},
            output="x",
            model="gpt-4.1-mini",
            provider="stub",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1000,
            estimated_cost=cost,
            status=ExecutionStatus.COMPLETED,
            created_at=now - timedelta(days=days_ago),
        )
        db.add(execution)
        await db.flush()
        db.add(
            EvaluationResult(
                execution_id=execution.id,
                relevance=score,
                completeness=score,
                format_compliance=score,
                overall_score=score,
                safety_passed=True,
                created_at=now - timedelta(days=days_ago),
            )
        )
        if decision is not None:
            db.add(
                HumanFeedback(
                    execution_id=execution.id,
                    user_id=user.id,
                    decision=decision,
                    approved=decision == FeedbackDecision.APPROVED,
                    edited=decision == FeedbackDecision.NEEDS_EDITING,
                    created_at=now - timedelta(days=days_ago),
                )
            )
    await db.commit()


async def test_adoption_counts_usage_and_effective_usage_separately(db, users, workflows):
    """Three people ran a workflow; only two produced an output anyone accepted."""
    await _seed(
        db,
        users,
        workflows,
        rows=[
            (users["employee"], 1, 90.0, FeedbackDecision.APPROVED, 0.01),
            (users["manager"], 2, 80.0, FeedbackDecision.APPROVED, 0.01),
            (users["outsider"], 3, 40.0, FeedbackDecision.REJECTED, 0.01),
        ],
    )
    summary = await analytics.adoption_summary(db, days=30)

    assert summary["total_employees"] == 4
    assert summary["active_users"] == 3
    assert summary["effective_users"] == 2
    assert summary["adoption_rate"] == 75.0
    assert summary["effective_adoption_rate"] == round(100 * 2 / 3, 1)
    assert summary["approval_rate"] == round(100 * 2 / 3, 1)


async def test_lapsed_users_count_as_licensed_but_not_active(db, users, workflows):
    await _seed(
        db,
        users,
        workflows,
        rows=[
            (users["employee"], 2, 90.0, FeedbackDecision.APPROVED, 0.01),
            (users["manager"], 70, 90.0, FeedbackDecision.APPROVED, 0.01),
        ],
    )
    summary = await analytics.adoption_summary(db, days=30)

    assert summary["licensed_users"] == 2  # ever used
    assert summary["active_users"] == 1  # used in the window


async def test_time_saved_is_credited_only_for_approved_outputs(db, users, workflows):
    """The workflow baseline is 20 manual minutes against 5 assisted minutes,
    so each approved output is credited with 15 estimated minutes."""
    await _seed(
        db,
        users,
        workflows,
        rows=[
            (users["employee"], 1, 90.0, FeedbackDecision.APPROVED, 0.01),
            (users["employee"], 1, 90.0, FeedbackDecision.APPROVED, 0.01),
            (users["employee"], 1, 90.0, FeedbackDecision.NEEDS_EDITING, 0.01),
            (users["employee"], 1, 90.0, None, 0.01),
        ],
    )
    summary = await analytics.adoption_summary(db, days=30)
    assert summary["estimated_minutes_saved"] == 30
    assert summary["estimated_hours_saved"] == 0.5


async def test_cost_per_approved_output_exceeds_cost_per_execution(db, users, workflows):
    await _seed(
        db,
        users,
        workflows,
        rows=[
            (users["employee"], 1, 90.0, FeedbackDecision.APPROVED, 0.10),
            (users["employee"], 1, 50.0, FeedbackDecision.REJECTED, 0.10),
        ],
    )
    summary = await analytics.adoption_summary(db, days=30)
    assert summary["estimated_spend"] == 0.2
    assert summary["cost_per_execution"] == 0.1
    assert summary["cost_per_approved_output"] == 0.2


async def test_quality_summary_reports_the_judge_human_gap(db, users, workflows):
    await _seed(
        db,
        users,
        workflows,
        rows=[
            (users["employee"], 1, 90.0, FeedbackDecision.APPROVED, 0.01),
            (users["employee"], 1, 90.0, FeedbackDecision.REJECTED, 0.01),
        ],
    )
    quality = await analytics.quality_summary(db, days=30)

    assert quality["overall_quality"] == 90.0
    assert quality["human_approval_rate"] == 50.0
    # The judge is 40 points more generous than the humans here, which is
    # exactly the signal keeping both layers is meant to surface.
    assert quality["judge_human_gap"] == 40.0


async def test_workflow_quality_flags_below_threshold_workflows(db, users, workflows):
    await _seed(
        db,
        users,
        workflows,
        rows=[(users["employee"], 1, 70.0, FeedbackDecision.REJECTED, 0.01)],
    )
    rows = await analytics.workflow_quality(db, days=30)
    row = next(item for item in rows if item["workflow_id"] == workflows["unit_tests"].id)

    assert row["needs_attention"] is True
    assert "below" in row["attention_reason"]


async def test_window_excludes_older_executions(db, users, workflows):
    await _seed(db, users, workflows, rows=[(users["employee"], 45, 90.0, None, 0.01)])

    assert (await analytics.adoption_summary(db, days=30))["executions"] == 0
    assert (await analytics.adoption_summary(db, days=90))["executions"] == 1


async def test_empty_database_returns_zeros_not_errors(db, users, workflows):
    summary = await analytics.adoption_summary(db, days=30)
    assert summary["executions"] == 0
    assert summary["adoption_rate"] == 0.0
    assert summary["cost_per_approved_output"] == 0.0

    quality = await analytics.quality_summary(db, days=30)
    assert quality["overall_quality"] is None
    assert quality["judge_human_gap"] is None


async def test_manager_sees_only_their_own_department(client, db, users, workflows):
    await _seed(db, users, workflows, rows=[(users["employee"], 1, 90.0, None, 0.01)])

    manager_token = await login(client, "manager@demo.com")
    rows = (await client.get("/analytics/departments", headers=auth(manager_token))).json()
    assert {row["department"] for row in rows} == {"Engineering"}

    admin_token = await login(client, "admin@demo.com")
    all_rows = (await client.get("/analytics/departments", headers=auth(admin_token))).json()
    assert {row["department"] for row in all_rows} == {"Engineering", "Finance"}


async def test_version_comparison_reports_the_delta(client, db, users, workflows):
    from sqlalchemy import select

    from app.models.workflow import WorkflowVersion

    admin_token = await login(client, "admin@demo.com")
    await client.post(
        f"/workflows/{workflows['unit_tests'].id}/versions",
        headers=auth(admin_token),
        json={
            "system_prompt": "Better prompt.",
            "prompt_template": "Code:\n$code",
            "changelog": "Tightened the format rules.",
            "activate": True,
        },
    )

    versions = (
        (
            await db.execute(
                select(WorkflowVersion)
                .where(WorkflowVersion.workflow_id == workflows["unit_tests"].id)
                .order_by(WorkflowVersion.version)
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    for version, score in ((versions[0], 70.0), (versions[1], 90.0)):
        execution = Execution(
            user_id=users["employee"].id,
            workflow_id=workflows["unit_tests"].id,
            workflow_version_id=version.id,
            inputs={},
            output="x",
            model="gpt-4.1-mini",
            provider="stub",
            estimated_cost=0.01,
            status=ExecutionStatus.COMPLETED,
            created_at=now,
        )
        db.add(execution)
        await db.flush()
        db.add(
            EvaluationResult(execution_id=execution.id, overall_score=score, safety_passed=True)
        )
    await db.commit()

    comparison = await analytics.version_comparison(db, workflows["unit_tests"])
    assert [v["version"] for v in comparison["versions"]] == [1, 2]
    assert comparison["versions"][0]["average_quality"] == 70.0
    assert comparison["versions"][1]["average_quality"] == 90.0
    assert "+20.0 points" in comparison["recommendation"]


async def test_recommendation_needs_two_scored_versions():
    assert "Not enough" in analytics.build_recommendation([])
    assert "Not enough" in analytics.build_recommendation(
        [{"version": 1, "executions": 3, "average_quality": 80.0, "average_cost": 0.0,
          "approval_rate": None}]
    )
