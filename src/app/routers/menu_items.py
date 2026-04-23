"""Menu item endpoints.

List/get are public. Creating a menu item is a staff-or-admin action
(staff expand the menu); updating and deleting are admin-only.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin, require_staff
from app.db import get_db
from app.models.category import Category
from app.models.menu_item import MenuItem
from app.models.price import Price
from app.schemas.menu_item import MenuItemCreate, MenuItemRead, MenuItemUpdate

router = APIRouter(prefix="/menu-items", tags=["menu-items"])


def _attach_current_price(db: Session, item: MenuItem) -> MenuItemRead:
    """Project a MenuItem + its current price into MenuItemRead.

    Single ``model_validate`` pass: we read the item's scalar columns
    directly off the ORM instance rather than going through the
    validate → dump → re-validate round trip just to stitch in one
    extra field.
    """
    current_price = db.scalar(
        select(Price.amount_cents)
        .where(Price.menu_item_id == item.id)
        .where(Price.effective_to.is_(None))
    )
    return MenuItemRead.model_validate(
        {
            "id": item.id,
            "category_id": item.category_id,
            "name": item.name,
            "description": item.description,
            "prep_time_minutes": item.prep_time_minutes,
            "is_daily_special": item.is_daily_special,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "current_price_cents": current_price,
        }
    )


@router.get("", response_model=list[MenuItemRead], summary="List menu items")
def list_items(
    db: Annotated[Session, Depends(get_db)],
    category_id: int | None = None,
    include_inactive: bool = False,
    daily_specials_only: bool = False,
) -> list[MenuItemRead]:
    """Return menu items with optional filters.

    By default only active items are returned — pass ``include_inactive``
    to include the rest. ``daily_specials_only`` filters to ``is_daily_special``.
    """
    stmt = select(MenuItem).order_by(MenuItem.name)
    if category_id is not None:
        stmt = stmt.where(MenuItem.category_id == category_id)
    if not include_inactive:
        stmt = stmt.where(MenuItem.is_active.is_(True))
    if daily_specials_only:
        stmt = stmt.where(MenuItem.is_daily_special.is_(True))
    items = db.scalars(stmt).all()
    return [_attach_current_price(db, it) for it in items]


@router.get("/{item_id}", response_model=MenuItemRead, summary="Fetch a single menu item")
def get_item(
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> MenuItemRead:
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    return _attach_current_price(db, item)


@router.post(
    "",
    response_model=MenuItemRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff)],
    summary="Create a menu item (staff or admin)",
)
def create_item(
    payload: MenuItemCreate,
    db: Annotated[Session, Depends(get_db)],
) -> MenuItemRead:
    """Create a new menu item.

    The item is created without a price — POST to ``/menu-items/{id}/prices``
    to set the first price. Items without a current price are considered
    unavailable for sale but may still appear in lists.
    """
    category = db.get(Category, payload.category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    item = MenuItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _attach_current_price(db, item)


@router.patch(
    "/{item_id}",
    response_model=MenuItemRead,
    dependencies=[Depends(require_admin)],
    summary="Update a menu item (admin)",
)
def update_item(
    item_id: int,
    payload: MenuItemUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> MenuItemRead:
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    updates = payload.model_dump(exclude_unset=True)
    if "category_id" in updates:
        if db.get(Category, updates["category_id"]) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _attach_current_price(db, item)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="Delete a menu item (admin)",
)
def delete_item(
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Hard-delete a menu item and cascade its price history.

    Items referenced by an archived menu cannot be deleted — the ON DELETE
    RESTRICT on ``menu_item_in_menu`` will raise an IntegrityError. In
    that case, deactivate the item (``is_active=false``) instead.
    """
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    db.delete(item)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Menu item is referenced by one or more menu snapshots; deactivate instead",
        ) from exc
