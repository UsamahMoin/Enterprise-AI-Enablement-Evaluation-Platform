"""Governance behaviour that depends on which provider a workflow is routed to.

Providers are not interchangeable. One keeps data inside the network but cannot
moderate; another moderates well but is an egress of data. These tests pin the
two consequences that follow.
"""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import DataClassification
from app.models.governance import GovernancePolicy, PolicyViolation
from app.services.ai.base import AIProvider, GenerationResponse, ModerationResult
from app.services.governance.policy import effective_classification, evaluate_request

SSN_INPUT = {"code": "# SSN 123-45-6789"}
EMAIL_INPUT = {"code": "# contact alex@acme-demo.test"}


class HostedProvider(AIProvider):
    """Stands in for a hosted frontier model: moderates, but data leaves."""

    name = "hosted-test"
    supports_moderation = True
    max_data_classification = DataClassification.CONFIDENTIAL
    keeps_data_in_house = False

    async def generate(self, request):  # pragma: no cover - not exercised here
        return GenerationResponse("", request.model, self.name, 0, 0, 0)

    async def moderate(self, text: str) -> ModerationResult:
        return ModerationResult(flagged=False, provider=self.name, available=True)


class SelfHostedProvider(AIProvider):
    """Stands in for Ollama: no moderation, but nothing leaves the network."""

    name = "local-test"
    supports_moderation = False
    max_data_classification = DataClassification.RESTRICTED
    keeps_data_in_house = True

    async def generate(self, request):  # pragma: no cover - not exercised here
        return GenerationResponse("", request.model, self.name, 0, 0, 0)


@pytest.fixture
def restricted_workflow(workflows):
    """A workflow the organisation has cleared for its most sensitive data."""
    workflow = workflows["unit_tests"]
    workflow.allowed_data_classification = DataClassification.RESTRICTED
    return workflow


def test_effective_limit_is_the_stricter_of_workflow_and_provider(restricted_workflow):
    assert (
        effective_classification(restricted_workflow, SelfHostedProvider())
        == DataClassification.RESTRICTED
    )
    # The workflow permits RESTRICTED, but a hosted provider may not receive it.
    assert (
        effective_classification(restricted_workflow, HostedProvider())
        == DataClassification.CONFIDENTIAL
    )


async def test_hosted_provider_caps_a_workflow_cleared_for_restricted_data(
    db, users, restricted_workflow
):
    decision = await evaluate_request(
        db,
        user=users["employee"],
        workflow=restricted_workflow,
        inputs=SSN_INPUT,
        provider=HostedProvider(),
        acknowledge_warnings=True,
    )

    assert decision.blocked is True
    assert decision.effective_classification == "CONFIDENTIAL"
    # The message must say *why* the limit applied, not just that it did.
    assert "hosted-test" in decision.reason
    assert "self-hosted" in decision.reason


async def test_same_request_is_permitted_on_a_self_hosted_provider(
    db, users, restricted_workflow
):
    """The routing decision is what raises the ceiling - not editing the workflow."""
    decision = await evaluate_request(
        db,
        user=users["employee"],
        workflow=restricted_workflow,
        inputs=SSN_INPUT,
        provider=SelfHostedProvider(),
        acknowledge_warnings=True,
    )

    assert decision.blocked is False
    assert decision.allowed is True
    assert decision.effective_classification == "RESTRICTED"


async def test_provider_cap_does_not_loosen_a_stricter_workflow(db, users, workflows):
    """A self-hosted provider does not let an INTERNAL workflow take an SSN."""
    decision = await evaluate_request(
        db,
        user=users["employee"],
        workflow=workflows["unit_tests"],  # INTERNAL
        inputs=SSN_INPUT,
        provider=SelfHostedProvider(),
        acknowledge_warnings=True,
    )

    assert decision.blocked is True
    assert decision.effective_classification == "INTERNAL"


async def test_unmoderatable_provider_records_not_checked_and_warns(
    db, users, workflows, monkeypatch
):
    monkeypatch.setattr(settings, "moderation_provider", "", raising=False)
    monkeypatch.setattr(settings, "moderation_fail_closed", False, raising=False)

    decision = await evaluate_request(
        db,
        user=users["employee"],
        workflow=workflows["unit_tests"],
        inputs={"code": "def add(a, b):\n    return a + b"},
        provider=SelfHostedProvider(),
        acknowledge_warnings=True,
    )

    assert decision.allowed is True
    assert decision.moderation_checked is False
    assert any("moderation was not performed" in w for w in decision.warnings)


async def test_moderation_can_be_delegated_to_another_provider(
    db, users, workflows, monkeypatch
):
    """Generate on a self-hosted model, moderate on one that can."""
    monkeypatch.setattr(settings, "moderation_provider", "stub", raising=False)

    decision = await evaluate_request(
        db,
        user=users["employee"],
        workflow=workflows["unit_tests"],
        inputs={"code": "def add(a, b):\n    return a + b"},
        provider=SelfHostedProvider(),
        acknowledge_warnings=True,
    )

    assert decision.moderation_checked is True
    assert decision.moderation_provider == "stub"


async def test_fail_closed_rejects_input_nobody_could_check(
    db, users, workflows, monkeypatch
):
    monkeypatch.setattr(settings, "moderation_provider", "", raising=False)
    monkeypatch.setattr(settings, "moderation_fail_closed", True, raising=False)

    decision = await evaluate_request(
        db,
        user=users["employee"],
        workflow=workflows["unit_tests"],
        inputs={"code": "def add(a, b):\n    return a + b"},
        provider=SelfHostedProvider(),
        acknowledge_warnings=True,
    )

    assert decision.blocked is True
    assert decision.policy_key == "content_moderation"
    assert "no moderation endpoint" in decision.reason

    violation = (await db.execute(select(PolicyViolation))).scalars().first()
    assert violation is not None
    assert violation.violation_type == "MODERATION"


async def test_fail_closed_is_ignored_when_the_policy_is_disabled(
    db, users, workflows, monkeypatch
):
    monkeypatch.setattr(settings, "moderation_fail_closed", True, raising=False)
    policy = (
        await db.execute(
            select(GovernancePolicy).where(GovernancePolicy.key == "content_moderation")
        )
    ).scalar_one()
    policy.enabled = False
    await db.commit()

    decision = await evaluate_request(
        db,
        user=users["employee"],
        workflow=workflows["unit_tests"],
        inputs={"code": "def add(a, b):\n    return a + b"},
        provider=SelfHostedProvider(),
        acknowledge_warnings=True,
    )

    assert decision.allowed is True
    assert decision.blocked is False


async def test_decision_records_which_provider_it_was_cleared_for(db, users, workflows):
    decision = await evaluate_request(
        db,
        user=users["employee"],
        workflow=workflows["unit_tests"],
        inputs=EMAIL_INPUT,
        provider=HostedProvider(),
        acknowledge_warnings=True,
    )

    assert decision.provider == "hosted-test"
    assert decision.as_dict()["effective_classification"] == "INTERNAL"
