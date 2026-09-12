"""Pre-execution governance pipeline.

    input -> PII check -> policy check -> moderation -> AI execution

A workflow only reaches the provider once every enabled blocking policy
passes. Violations are recorded for audit with categories, never values.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import DataClassification, RiskLevel, ViolationType
from app.models.governance import GovernancePolicy, PolicyViolation
from app.models.user import User
from app.models.workflow import Workflow
from app.services.ai.base import AIProvider
from app.services.ai.factory import get_moderation_provider
from app.services.governance.pii import (
    CLASSIFICATION_RANK,
    Detection,
    exceeds_classification,
    scan_inputs,
)

POLICY_SENSITIVE_DATA = "sensitive_data_detection"
POLICY_PROHIBITED_USE = "prohibited_use"
POLICY_MODERATION = "content_moderation"
POLICY_HUMAN_REVIEW = "high_risk_human_review"


@dataclass
class GovernanceDecision:
    allowed: bool = True
    blocked: bool = False
    reason: str = ""
    policy_key: str = ""
    violation_type: str = ""
    severity: str = RiskLevel.MEDIUM
    detections: list[Detection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requires_human_review: bool = False
    # Which provider the request was cleared for, and the classification cap
    # that actually applied once the provider's own limit was taken into account.
    provider: str = ""
    effective_classification: str = ""
    # False when no provider could moderate the input. Distinct from "moderated
    # and found clean" - the UI and the audit record keep them apart.
    moderation_checked: bool = True
    moderation_provider: str = ""

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "blocked": self.blocked,
            "reason": self.reason,
            "policy_key": self.policy_key,
            "detections": [
                {"type": d.type, "label": d.label, "count": d.count, "field": d.field}
                for d in self.detections
            ],
            "warnings": self.warnings,
            "requires_human_review": self.requires_human_review,
            "provider": self.provider,
            "effective_classification": self.effective_classification,
            "moderation_checked": self.moderation_checked,
            "moderation_provider": self.moderation_provider,
        }


def _rank(classification: DataClassification | str) -> int:
    return CLASSIFICATION_RANK[DataClassification(classification)]


def effective_classification(
    workflow: Workflow, provider: AIProvider
) -> DataClassification:
    """The stricter of the workflow's approved limit and the provider's own."""
    workflow_limit = DataClassification(workflow.allowed_data_classification)
    provider_limit = DataClassification(provider.max_data_classification)
    return workflow_limit if _rank(workflow_limit) <= _rank(provider_limit) else provider_limit


async def load_policies(db: AsyncSession) -> dict[str, GovernancePolicy]:
    rows = (await db.execute(select(GovernancePolicy))).scalars().all()
    return {policy.key: policy for policy in rows}


def _enabled(policies: dict[str, GovernancePolicy], key: str) -> bool:
    policy = policies.get(key)
    return policy is None or policy.enabled


def _blocking(policies: dict[str, GovernancePolicy], key: str, default: bool = True) -> bool:
    policy = policies.get(key)
    return policy.blocking if policy else default


async def evaluate_request(
    db: AsyncSession,
    *,
    user: User,
    workflow: Workflow,
    inputs: dict,
    provider: AIProvider,
    acknowledge_warnings: bool = False,
    record_violations: bool = True,
) -> GovernanceDecision:
    """Run the full pre-flight pipeline for one execution request.

    `record_violations=False` runs the same checks without writing audit rows,
    which is what benchmark runs need: a synthetic case that is *supposed* to
    be blocked is not a real policy breach by a real person.
    """
    policies = await load_policies(db)
    decision = GovernanceDecision(
        requires_human_review=workflow.requires_human_review
        or workflow.risk_level == RiskLevel.HIGH,
        provider=provider.name,
        effective_classification=str(effective_classification(workflow, provider)),
    )

    # 1. Prohibited use ---------------------------------------------------
    if _enabled(policies, POLICY_PROHIBITED_USE) and workflow.risk_level == RiskLevel.PROHIBITED:
        decision.allowed = False
        decision.blocked = True
        decision.policy_key = POLICY_PROHIBITED_USE
        decision.violation_type = ViolationType.PROHIBITED_USE
        decision.severity = RiskLevel.PROHIBITED
        decision.reason = (
            "This use case is classified PROHIBITED and cannot be executed on the platform."
        )
        return decision

    # 2. Sensitive data ---------------------------------------------------
    if _enabled(policies, POLICY_SENSITIVE_DATA):
        detections = scan_inputs(inputs)
        decision.detections = detections

        # The effective limit is the stricter of what the workflow is approved
        # for and what the provider may receive. A hosted provider is an egress
        # of data, so it caps below a self-hosted one no matter what the
        # workflow permits - routing the same workflow to a local model is what
        # raises the ceiling, not editing the workflow.
        allowed_classification = effective_classification(workflow, provider)
        decision.effective_classification = str(allowed_classification)
        over_limit = [d for d in detections if exceeds_classification(d, allowed_classification)]

        if over_limit and _blocking(policies, POLICY_SENSITIVE_DATA):
            labels = ", ".join(sorted({d.label for d in over_limit}))
            workflow_limit = DataClassification(workflow.allowed_data_classification)
            decision.allowed = False
            decision.blocked = True
            decision.policy_key = POLICY_SENSITIVE_DATA
            decision.violation_type = ViolationType.SENSITIVE_DATA
            decision.severity = RiskLevel.HIGH
            decision.reason = (
                f"Potential sensitive information detected: {labels}. "
                f"This workflow is approved for {allowed_classification.value} data only, "
                "so the request was not sent to the AI provider."
            )
            if _rank(provider.max_data_classification) < _rank(workflow_limit):
                decision.reason += (
                    f" The limit is set by the '{provider.name}' provider, which may "
                    f"receive {provider.max_data_classification.value} data at most; "
                    "routing this workflow to a self-hosted model would raise it."
                )
            if record_violations:
                await record_violation(db, decision, user=user, workflow=workflow)
            return decision

        for detection in detections:
            if detection not in over_limit:
                decision.warnings.append(
                    f"{detection.label} detected in '{detection.field}' "
                    f"({detection.count}). Permitted for this workflow, but avoid "
                    "sending personal data you do not need."
                )

    # 3. Moderation -------------------------------------------------------
    if _enabled(policies, POLICY_MODERATION):
        joined = "\n".join(str(value) for value in (inputs or {}).values())
        moderator = get_moderation_provider(provider)

        if moderator is None:
            # No provider could check the input. This is recorded as *not
            # checked*; it must never be presented as a clean result.
            decision.moderation_checked = False
            if _blocking(policies, POLICY_MODERATION) and settings.moderation_fail_closed:
                decision.allowed = False
                decision.blocked = True
                decision.policy_key = POLICY_MODERATION
                decision.violation_type = ViolationType.MODERATION
                decision.severity = RiskLevel.HIGH
                decision.reason = (
                    f"The '{provider.name}' provider has no moderation endpoint and no "
                    "fallback moderator is configured. The moderation policy is set to "
                    "fail closed, so the request was not sent."
                )
                if record_violations:
                    await record_violation(db, decision, user=user, workflow=workflow)
                return decision
            decision.warnings.append(
                f"Content moderation was not performed: the '{provider.name}' provider "
                "has no moderation endpoint. Set MODERATION_PROVIDER to delegate the "
                "check, or MODERATION_FAIL_CLOSED=true to reject unchecked input."
            )
            result = None
        else:
            decision.moderation_provider = moderator.name
            result = await moderator.moderate(joined)
            decision.moderation_checked = result.available

        if result is not None and result.flagged:
            decision.allowed = False
            decision.blocked = True
            decision.policy_key = POLICY_MODERATION
            decision.violation_type = ViolationType.MODERATION
            decision.severity = RiskLevel.HIGH
            decision.reason = (
                "Input was flagged by the content moderation check "
                f"({', '.join(result.categories) or 'policy violation'})."
            )
            if record_violations:
                await record_violation(db, decision, user=user, workflow=workflow)
            return decision

    # 4. Warnings acknowledgement ----------------------------------------
    if decision.warnings and not acknowledge_warnings:
        decision.allowed = False
        decision.blocked = False
        decision.policy_key = POLICY_SENSITIVE_DATA
        decision.reason = "Review the sensitive-data warnings before running this workflow."

    return decision


async def record_violation(
    db: AsyncSession,
    decision: GovernanceDecision,
    *,
    user: User | None,
    workflow: Workflow | None,
    execution_id: str | None = None,
) -> PolicyViolation:
    violation = PolicyViolation(
        user_id=user.id if user else None,
        workflow_id=workflow.id if workflow else None,
        execution_id=execution_id,
        policy_key=decision.policy_key,
        violation_type=decision.violation_type or ViolationType.SENSITIVE_DATA,
        severity=decision.severity,
        blocked=decision.blocked,
        details={
            "detections": [
                {"type": d.type, "count": d.count, "field": d.field}
                for d in decision.detections
            ],
            "reason": decision.reason,
        },
    )
    db.add(violation)
    await db.flush()
    return violation


DEFAULT_POLICIES = [
    {
        "key": POLICY_SENSITIVE_DATA,
        "name": "Sensitive data detection",
        "description": (
            "Scans workflow input for SSN-like values, payment card numbers, secrets, "
            "email addresses and phone numbers. Blocks when the category exceeds the "
            "data classification the workflow is approved for."
        ),
        "risk_level": RiskLevel.HIGH,
        "blocking": True,
    },
    {
        "key": POLICY_PROHIBITED_USE,
        "name": "Prohibited use cases",
        "description": (
            "Blocks workflows classified PROHIBITED, such as fully automated adverse "
            "employment decisions."
        ),
        "risk_level": RiskLevel.PROHIBITED,
        "blocking": True,
    },
    {
        "key": POLICY_MODERATION,
        "name": "Content moderation",
        "description": "Screens input through the provider moderation endpoint before generation.",
        "risk_level": RiskLevel.MEDIUM,
        "blocking": True,
    },
    {
        "key": POLICY_HUMAN_REVIEW,
        "name": "Human review for high-risk workflows",
        "description": (
            "HIGH risk workflows require an explicit human approve/edit/reject decision "
            "before the output is treated as usable."
        ),
        "risk_level": RiskLevel.HIGH,
        "blocking": False,
    },
]
