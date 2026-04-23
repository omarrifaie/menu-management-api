"""Category request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    display_order: int = 0
    is_active: bool = True


class CategoryCreate(CategoryBase):
    """Payload for ``POST /categories``."""


class CategoryUpdate(BaseModel):
    """Partial update payload for ``PATCH /categories/{id}``."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    display_order: int | None = None
    is_active: bool | None = None


class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
