"""Category endpoints.

Reads are public; writes require an admin JWT. Deletes are blocked while a
category still owns active menu items — callers should flip ``is_active``
to hide a category from customers instead of removing it outright.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.db import get_db
from app.models.category import Category
from app.models.menu_item import MenuItem
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead], summary="List categories")
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    include_inactive: bool = False,
) -> list[CategoryRead]:
    """Return every category, ordered by ``display_order`` then ``name``.

    Inactive categories are hidden by default to mirror what a customer
    would see; pass ``?include_inactive=true`` to include them.
    """
    stmt = select(Category).order_by(Category.display_order, Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))
    rows = db.scalars(stmt).all()
    return [CategoryRead.model_validate(c) for c in rows]


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Create a category (admin)",
)
def create_category(
    payload: CategoryCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryRead:
    """Create a new category. The ``name`` column is unique."""
    existing = db.scalar(select(Category).where(Category.name == payload.name))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Category name already in use")
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryRead.model_validate(category)


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    dependencies=[Depends(require_admin)],
    summary="Update a category (admin)",
)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CategoryRead:
    """Partial update — only non-null fields are applied."""
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return CategoryRead.model_validate(category)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="Delete a category (admin)",
)
def delete_category(
    category_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Hard-delete a category.

    Fails with 409 if any active menu items still point at it. Deactivate
    or reassign those items first. (Inactive items are ignored — they
    can't be shown to customers anyway.)
    """
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")

    active_children = db.scalar(
        select(MenuItem)
        .where(MenuItem.category_id == category_id)
        .where(MenuItem.is_active.is_(True))
        .limit(1)
    )
    if active_children is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Category still has active menu items; deactivate them first",
        )

    db.delete(category)
    db.commit()
