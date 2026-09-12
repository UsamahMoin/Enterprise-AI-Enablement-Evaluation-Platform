"""End-to-end workflow execution, governance blocking and human feedback."""

from sqlalchemy import select

from app.core.enums import ExecutionStatus
from app.models.execution import Execution
from app.models.governance import GovernancePolicy, PolicyViolation
from tests.conftest import auth, login

CODE = "def calculate_total(items):\n    return sum(items)"


async def run_workflow(client, token, workflow_id, inputs, acknowledge=False):
    return await client.post(
        "/executions",
        headers=auth(token),
        json={
            "workflow_id": workflow_id,
            "inputs": inputs,
            "acknowledge_warnings": acknowledge,
        },
    )


async def test_execution_records_output_cost_and_evaluation(client, workflows, users):
    token = await login(client, "employee@demo.com")
    response = await run_workflow(client, token, workflows["unit_tests"].id, {"code": CODE})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["output"]
    assert body["input_tokens"] > 0 and body["output_tokens"] > 0
    assert body["latency_ms"] > 0
    assert body["estimated_cost"] > 0
    assert body["workflow_version"] == 1

    evaluation = body["evaluation"]
    assert evaluation is not None
    assert 0 <= evaluation["overall_score"] <= 100
    assert evaluation["format_compliance"] is not None
    # This workflow supplies no reference material, so groundedness is N/A
    # rather than a guessed number.
    assert evaluation["groundedness"] is None
    assert any(check["name"] == "code_syntax" for check in evaluation["deterministic_checks"])


async def test_prohibited_workflow_is_blocked_before_the_provider(client, workflows, users, db):
    token = await login(client, "employee@demo.com")
    response = await run_workflow(
        client, token, workflows["prohibited"].id, {"application": "CV text"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "BLOCKED"
    assert "PROHIBITED" in body["blocked_reason"]
    assert body["output"] == ""

    stored = (await db.execute(select(Execution).where(Execution.id == body["id"]))).scalar_one()
    assert stored.inputs == {}  # blocked input is not persisted


async def test_sensitive_data_blocks_and_is_audited_without_storing_the_value(
    client, workflows, users, db
):
    token = await login(client, "employee@demo.com")
    response = await run_workflow(
        client,
        token,
        workflows["unit_tests"].id,
        {"code": "# customer SSN 123-45-6789\n" + CODE},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == ExecutionStatus.BLOCKED
    assert "Social Security Number" in body["blocked_reason"]

    violation = (await db.execute(select(PolicyViolation))).scalars().first()
    assert violation is not None
    assert violation.violation_type == "SENSITIVE_DATA"
    assert violation.blocked is True
    assert violation.details["detections"][0]["type"] == "SSN"
    # The audit record keeps the category, never the value.
    assert "123-45-6789" not in str(violation.details)


async def test_disabling_the_policy_lets_the_request_through(client, workflows, users, db):
    """Governance is configuration, and the effect of changing it is visible."""
    policy = (
        await db.execute(
            select(GovernancePolicy).where(GovernancePolicy.key == "sensitive_data_detection")
        )
    ).scalar_one()
    policy.enabled = False
    await db.commit()

    token = await login(client, "employee@demo.com")
    response = await run_workflow(
        client, token, workflows["unit_tests"].id, {"code": "# SSN 123-45-6789\n" + CODE}
    )
    assert response.json()["status"] == "COMPLETED"


async def test_warnings_require_acknowledgement_then_proceed(client, workflows, users):
    """An email address is permitted for an INTERNAL workflow, but the user is
    told about it before the request is sent."""
    token = await login(client, "employee@demo.com")
    inputs = {"code": "# contact alex@acme-demo.test\n" + CODE}

    first = await run_workflow(client, token, workflows["unit_tests"].id, inputs)
    assert first.status_code == 409
    detail = first.json()["detail"]
    assert detail["warnings"]
    assert detail["blocked"] is False

    second = await run_workflow(client, token, workflows["unit_tests"].id, inputs, acknowledge=True)
    assert second.status_code == 201
    assert second.json()["status"] == "COMPLETED"


async def test_feedback_is_recorded_and_returned_with_the_execution(client, workflows, users):
    token = await login(client, "employee@demo.com")
    execution_id = (
        await run_workflow(client, token, workflows["unit_tests"].id, {"code": CODE})
    ).json()["id"]

    feedback = await client.post(
        f"/executions/{execution_id}/feedback",
        headers=auth(token),
        json={"decision": "APPROVED", "rating": 5, "comment": "Used as is."},
    )
    assert feedback.status_code == 201
    assert feedback.json()["approved"] is True

    fetched = await client.get(f"/executions/{execution_id}", headers=auth(token))
    assert fetched.json()["feedback"]["rating"] == 5


async def test_needs_editing_is_not_counted_as_an_approval(client, workflows, users):
    token = await login(client, "employee@demo.com")
    execution_id = (
        await run_workflow(client, token, workflows["unit_tests"].id, {"code": CODE})
    ).json()["id"]

    response = await client.post(
        f"/executions/{execution_id}/feedback",
        headers=auth(token),
        json={"decision": "NEEDS_EDITING", "rating": 3},
    )
    body = response.json()
    assert body["approved"] is False
    assert body["edited"] is True


async def test_employees_see_only_their_own_executions(client, workflows, users):
    employee_token = await login(client, "employee@demo.com")
    outsider_token = await login(client, "outsider@demo.com")

    execution_id = (
        await run_workflow(client, employee_token, workflows["unit_tests"].id, {"code": CODE})
    ).json()["id"]

    mine = await client.get("/executions", headers=auth(employee_token))
    assert [item["id"] for item in mine.json()] == [execution_id]

    theirs = await client.get("/executions", headers=auth(outsider_token))
    assert theirs.json() == []

    forbidden = await client.get(f"/executions/{execution_id}", headers=auth(outsider_token))
    assert forbidden.status_code == 403


async def test_admin_can_view_any_execution(client, workflows, users):
    employee_token = await login(client, "employee@demo.com")
    admin_token = await login(client, "admin@demo.com")
    execution_id = (
        await run_workflow(client, employee_token, workflows["unit_tests"].id, {"code": CODE})
    ).json()["id"]

    response = await client.get(f"/executions/{execution_id}", headers=auth(admin_token))
    assert response.status_code == 200


async def test_re_evaluation_is_idempotent_for_one_execution(client, workflows, users, db):
    token = await login(client, "employee@demo.com")
    execution_id = (
        await run_workflow(client, token, workflows["unit_tests"].id, {"code": CODE})
    ).json()["id"]

    await client.post(f"/executions/{execution_id}/evaluate", headers=auth(token))
    await client.post(f"/executions/{execution_id}/evaluate", headers=auth(token))

    from app.models.execution import EvaluationResult

    rows = (
        await db.execute(
            select(EvaluationResult).where(EvaluationResult.execution_id == execution_id)
        )
    ).scalars().all()
    assert len(rows) == 1
