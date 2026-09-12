from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey


class TrainingModule(UUIDPrimaryKey, TimestampMixin, Base):
    """Short enablement lesson - the platform teaches, not just executes."""

    __tablename__ = "training_modules"

    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    target_roles: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class TrainingCompletion(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "training_completions"
    __table_args__ = (UniqueConstraint("user_id", "module_id", name="uq_training_completion"),)

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False
    )
