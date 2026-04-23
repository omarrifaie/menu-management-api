"""Price model — one row per pricing epoch for a menu item.

The "current" price for an item is the row whose ``effective_to`` is NULL.
POSTing a new price closes the open row (sets its ``effective_to`` to now)
and inserts a fresh one. Historical rows are never mutated, so archived
menus that reference them stay faithful forever.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    menu_item: Mapped[MenuItem] = relationship(back_populates="prices")  # noqa: F821

    __table_args__ = (
        # Helps the "give me the current price for each item" query.
        Index("ix_prices_item_open", "menu_item_id", "effective_to"),
    )

    @property
    def is_current(self) -> bool:
        return self.effective_to is None

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Price id={self.id} item={self.menu_item_id} "
            f"amount={self.amount_cents}¢ current={self.is_current}>"
        )
