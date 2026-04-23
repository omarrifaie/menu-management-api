"""Menu item model — a dish, drink, or other purchasable thing."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    prep_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_daily_special: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    category: Mapped[Category] = relationship(  # noqa: F821
        back_populates="items",
        lazy="joined",
    )
    prices: Mapped[list[Price]] = relationship(  # noqa: F821
        back_populates="menu_item",
        cascade="all, delete-orphan",
        order_by="Price.effective_from.desc()",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MenuItem id={self.id} name={self.name!r}>"
