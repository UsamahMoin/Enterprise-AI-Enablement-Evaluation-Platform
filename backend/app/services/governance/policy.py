"""Pre-execution governance pipeline.

    input -> PII check -> policy check -> moderation -> AI execution

A workflow only reaches the provider once every enabled blocking policy
passes. Violations are recorded for audit with categories, never values.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DataClassification, RiskLevel, ViolationType
from app.models.governance import GovernancePolicy, PolicyViolation
from app.models.user import User
from app.models.workflow import Workflow
from app.services.ai.base import AIProvider
from app.services.governance.pii import Detection, exceeds_classification, scan_inputs

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
        }


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
) -> GovernanceDecision:
    """Run the full pre-flight pipeline for one execution request."""
    policies = await load_policies(db)
    decision = GovernanceDecision(
        requires_human_review=workflow.requires_human_review
        or workflow.risk_level == RiskLevel.HIGH
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
        allowed_classification = DataClassification(workflow.allowed_data_classification)
        over_limit = [d for d in detections if exceeds_classification(d, allowed_classification)]

        if over_limit and _blocking(policies, POLICY_SENSITIVE_DATA):
            labels = ", ".join(sorted({d.label for d in over_limit}))
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
        result = await provider.moderate(joined)
        if result.flagged:
            decision.allowed = False
            decision.blocked = True
            decision.policy_key = POLICY_MODERATION
            decision.violation_type = ViolationType.MODERATION
            decision.severity = RiskLevel.HIGH
            decision.reason = (
                "Input was flagged by the content moderation check "
                f"({', '.join(result.categories) or 'policy violation'})."
            )
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
