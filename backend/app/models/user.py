from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import SystemRole
from app.models.base import TimestampMixin, UUIDPrimaryKey
from app.models.organization import Department


class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)

    department_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    # Functional role used to recommend workflows (e.g. "Developer", "HR").
    job_role: Mapped[str] = mapped_column(String(60), nullable=False, default="Employee")
    # Authorisation role inside the platform.
    system_role: Mapped[str] = mapped_column(String(20), nullable=False, default=SystemRole.EMPLOYEE)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    department: Mapped[Department | None] = relationship(back_populates="users")
