from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.enums import RiskLevel
from app.models.base import TimestampMixin, UUIDPrimaryKey


class GovernancePolicy(UUIDPrimaryKey, TimestampMixin, Base):
    """An organisation-level rule applied before a workflow may execute."""

    __tablename__ = "governance_policies"

    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default=RiskLevel.MEDIUM)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Blocking policies stop execution; non-blocking ones warn and log.
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PolicyViolation(UUIDPrimaryKey, TimestampMixin, Base):
    """Audit record. Stores detector findings, never the sensitive value."""

    __tablename__ = "policy_violations"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True
    )
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    policy_key: Mapped[str] = mapped_column(String(80), nullable=False)
    violation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default=RiskLevel.MEDIUM)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # e.g. {"detections": [{"type": "SSN", "count": 1}]} - categories only.
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
