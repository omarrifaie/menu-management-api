"""Menu + MenuItemInMenu snapshot table.

A Menu is a named, versioned collection of items published at a point in
time. Publishing a new version does not mutate earlier ones — each Menu
carries its own rows in ``menu_item_in_menu`` pointing at the specific
``Price.id`` that was current when the menu was published. That's how an
archived menu can still render its original prices after pricing changes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow


class Menu(Base):
    __tablename__ = "menus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # ondelete="RESTRICT" preserves the audit trail — a user who has ever
    # published a menu cannot be deleted without first reassigning or
    # removing those rows.
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    entries: Mapped[list[MenuItemInMenu]] = relationship(
        back_populates="menu",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (UniqueConstraint("name", "version", name="uq_menu_name_version"),)

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Menu id={self.id} name={self.name!r} v{self.version}>"


class MenuItemInMenu(Base):
    """Snapshot row — freezes (menu, item, price) at publish time.

    Fidelity caveat: only the *price* is frozen via ``price_id``. The
    item's ``name``, ``description``, and ``prep_time_minutes`` are read
    live from :class:`MenuItem` when a menu is rendered, so edits to
    those fields will show up in previously-archived menus. This is a
    deliberate trade-off — menu snapshots preserve what customers paid,
    not every cosmetic field. See README "Versioned menu archives" for
    more.
    """

    __tablename__ = "menu_item_in_menu"

    menu_id: Mapped[int] = mapped_column(
        ForeignKey("menus.id", ondelete="CASCADE"),
        primary_key=True,
    )
    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    price_id: Mapped[int] = mapped_column(
        ForeignKey("prices.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    menu: Mapped[Menu] = relationship(back_populates="entries")
    menu_item: Mapped[MenuItem] = relationship(lazy="joined")  # noqa: F821
    price: Mapped[Price] = relationship(lazy="joined")  # noqa: F821
