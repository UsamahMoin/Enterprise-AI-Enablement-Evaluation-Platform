from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import ExecutionStatus
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Execution(UUIDPrimaryKey, TimestampMixin, Base):
    """One run of one workflow version by one user."""

    __tablename__ = "executions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False
    )

    inputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rendered_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output: Mapped[str] = mapped_column(Text, nullable=False, default="")

    model: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExecutionStatus.PENDING, index=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    evaluation: Mapped["EvaluationResult | None"] = relationship(
        back_populates="execution", cascade="all, delete-orphan", uselist=False
    )
    feedback: Mapped["HumanFeedback | None"] = relationship(
        back_populates="execution", cascade="all, delete-orphan", uselist=False
    )


class EvaluationResult(UUIDPrimaryKey, TimestampMixin, Base):
    """Combined deterministic + model-based scores for one execution."""

    __tablename__ = "evaluation_results"

    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    groundedness: Mapped[float | None] = mapped_column(Float, nullable=True)
    format_compliance: Mapped[float | None] = mapped_column(Float, nullable=True)
    clarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # False when no provider in the chain could moderate the output. Kept
    # separate from safety_passed so "not checked" is never read as "passed".
    safety_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    deterministic_checks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evaluation_model: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    evaluation_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    evaluation_reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rubric_used: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    execution: Mapped[Execution] = relationship(back_populates="evaluation")


class HumanFeedback(UUIDPrimaryKey, TimestampMixin, Base):
    """Human judgement is retained deliberately: an AI judge is not ground truth."""

    __tablename__ = "human_feedback"

    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    thumbs_up: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")

    execution: Mapped[Execution] = relationship(back_populates="feedback")


class UsageMetric(UUIDPrimaryKey, Base):
    """Daily per-user rollup, kept so adoption queries stay cheap."""

    __tablename__ = "usage_metrics"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    day: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    executions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_executions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_minutes_saved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
