"""Menu item request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MenuItemBase(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    prep_time_minutes: int = Field(default=0, ge=0, le=600)
    is_daily_special: bool = False
    is_active: bool = True


class MenuItemCreate(MenuItemBase):
    """Payload for ``POST /menu-items``."""


class MenuItemUpdate(BaseModel):
    """Partial update for ``PATCH /menu-items/{id}`` (admin only)."""

    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    prep_time_minutes: int | None = Field(default=None, ge=0, le=600)
    is_daily_special: bool | None = None
    is_active: bool | None = None


class MenuItemRead(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    current_price_cents: int | None = Field(
        default=None,
        description="Current (open-ended) price in cents, or null if the item has no active price.",
    )
