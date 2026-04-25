"""Menu request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MenuCreate(BaseModel):
    """Payload for ``POST /menus`` — publishes a new menu version.

    The server snapshots every active menu item whose id is in ``item_ids``
    together with that item's currently-open price, writing one row per
    item into ``menu_item_in_menu``. The version number is auto-assigned
    as ``max(version) + 1`` across menus sharing the same ``name``.
    """

    name: str = Field(min_length=1, max_length=150)
    item_ids: list[int] = Field(min_length=1, description="IDs of MenuItems to snapshot.")


class MenuRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: int
    published_at: datetime
    archived_at: datetime | None
    created_by: int
    archived_by: int | None = None


class MenuEntryRead(BaseModel):
    """A single (item, price) snapshot row inside a menu."""

    menu_item_id: int
    name: str
    description: str | None
    category_id: int
    amount_cents: int
    prep_time_minutes: int
