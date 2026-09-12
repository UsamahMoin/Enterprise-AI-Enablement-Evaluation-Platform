from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import DataClassification, RiskLevel, WorkflowStatus
from app.models.base import TimestampMixin, UUIDPrimaryKey


class Workflow(UUIDPrimaryKey, TimestampMixin, Base):
    """An approved, governed AI task template - not a free-text chat box."""

    __tablename__ = "workflows"

    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    department: Mapped[str] = mapped_column(String(80), nullable=False)
    target_role: Mapped[str] = mapped_column(String(60), nullable=False)
    task_type: Mapped[str] = mapped_column(String(60), nullable=False, default="generation")

    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default=RiskLevel.LOW)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=WorkflowStatus.ACTIVE)
    requires_human_review: Mapped[bool] = mapped_column(default=False, nullable=False)
    allowed_data_classification: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DataClassification.INTERNAL
    )
    expected_output_format: Mapped[str] = mapped_column(String(20), nullable=False, default="text")

    # Minutes the same task is assumed to take unaided. Drives the *estimated*
    # time-saved metric; deliberately stored per workflow rather than guessed.
    estimated_manual_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    estimated_assisted_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Input field definitions rendered by the frontend.
    input_schema: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # "When to use / when not to use" enablement guidance.
    guidance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    versions: Mapped[list["WorkflowVersion"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan", order_by="WorkflowVersion.version"
    )


class WorkflowVersion(UUIDPrimaryKey, TimestampMixin, Base):
    """Prompts are versioned, never overwritten, so quality can be compared."""

    __tablename__ = "workflow_versions"
    __table_args__ = (UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),)

    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False, default="gpt-4.1-mini")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    # Per-workflow rubric: dimension weights + deterministic check config.
    evaluation_rubric: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    changelog: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)

    workflow: Mapped[Workflow] = relationship(back_populates="versions")
