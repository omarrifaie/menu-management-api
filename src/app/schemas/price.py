"""Price request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PriceCreate(BaseModel):
    """Payload for ``POST /menu-items/{id}/prices`` (admin only).

    The new price takes effect immediately; any currently-open price for
    this item will have its ``effective_to`` closed to the same moment.
    """

    amount_cents: int = Field(gt=0, le=10_000_000, description="Price in cents (integer).")


class PriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int
    amount_cents: int
    effective_from: datetime
    effective_to: datetime | None
    created_by: int
