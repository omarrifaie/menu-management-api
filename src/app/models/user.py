"""User model and role enum."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


# Intentionally `(str, enum.Enum)` rather than `enum.StrEnum` (UP042 off):
# Pydantic's validation of role values via this class is already
# well-tested; switching the base class would subtly change __str__ /
# equality semantics and is not worth the churn. Revisit when bumping
# the minimum Python version.
class UserRole(str, enum.Enum):  # noqa: UP042
    """Application roles.

    Stored as a string in the database so values remain human-readable in
    psql/sqlite3 inspection and migrations don't need to reshuffle enum
    ordinals.
    """

    ADMIN = "admin"
    STAFF = "staff"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=16),
        nullable=False,
        default=UserRole.STAFF,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
