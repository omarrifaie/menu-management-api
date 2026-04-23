"""Menu endpoints.

A Menu is a snapshot — publishing freezes each item's current price into
``menu_item_in_menu``, so archived menus continue to render their original
prices even after those prices are later superseded.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.db import get_db
from app.models.menu import Menu, MenuItemInMenu
from app.models.menu_item import MenuItem
from app.models.price import Price
from app.models.user import User
from app.schemas.menu import MenuCreate, MenuEntryRead, MenuRead

router = APIRouter(prefix="/menus", tags=["menus"])


@router.get("", response_model=list[MenuRead], summary="List menus")
def list_menus(
    db: Annotated[Session, Depends(get_db)],
    include_archived: bool = True,
) -> list[MenuRead]:
    """Return every menu, newest first.

    ``include_archived=false`` filters out any menu with a non-null
    ``archived_at`` — useful for "what are we serving right now?" UIs.
    """
    stmt = select(Menu).order_by(Menu.published_at.desc())
    if not include_archived:
        stmt = stmt.where(Menu.archived_at.is_(None))
    return [MenuRead.model_validate(m) for m in db.scalars(stmt).all()]


@router.get("/{menu_id}", response_model=MenuRead, summary="Fetch a single menu")
def get_menu(menu_id: int, db: Annotated[Session, Depends(get_db)]) -> MenuRead:
    menu = db.get(Menu, menu_id)
    if menu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu not found")
    return MenuRead.model_validate(menu)


@router.get(
    "/{menu_id}/items",
    response_model=list[MenuEntryRead],
    summary="Return the frozen items+prices for a menu",
)
def get_menu_items(menu_id: int, db: Annotated[Session, Depends(get_db)]) -> list[MenuEntryRead]:
    """Render a menu as the customer would have seen it when it was published.

    Even if the underlying ``Price`` rows for these items have since been
    superseded, the rows returned here reflect exactly what was snapshotted
    at publish time.
    """
    menu = db.get(Menu, menu_id)
    if menu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu not found")

    entries: list[MenuEntryRead] = []
    for entry in menu.entries:
        entries.append(
            MenuEntryRead(
                menu_item_id=entry.menu_item.id,
                name=entry.menu_item.name,
                description=entry.menu_item.description,
                category_id=entry.menu_item.category_id,
                amount_cents=entry.price.amount_cents,
                prep_time_minutes=entry.menu_item.prep_time_minutes,
            )
        )
    return entries


@router.post(
    "",
    response_model=MenuRead,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a new menu version (admin)",
)
def publish_menu(
    payload: MenuCreate,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> MenuRead:
    """Create a new :class:`Menu` and snapshot its items.

    For each item id in ``item_ids``:

    * Verify the item exists and is active.
    * Look up its currently-open price (``effective_to IS NULL``).
    * Write a ``menu_item_in_menu`` row tying the three together.

    Fails with 422 if any referenced item has no active price — the menu
    would be unable to quote a price to customers.
    """
    next_version = (
        db.scalar(select(func.coalesce(func.max(Menu.version), 0)).where(Menu.name == payload.name))
        or 0
    ) + 1

    if len(set(payload.item_ids)) != len(payload.item_ids):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Duplicate item ids in payload",
        )

    menu = Menu(
        name=payload.name,
        version=next_version,
        published_at=datetime.now(UTC),
        created_by=admin.id,
    )
    db.add(menu)
    db.flush()  # populate menu.id for the FK on menu_item_in_menu rows

    for item_id in payload.item_ids:
        item = db.get(MenuItem, item_id)
        if item is None or not item.is_active:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Menu item {item_id} is missing or inactive",
            )
        current_price = db.scalar(
            select(Price)
            .where(Price.menu_item_id == item_id)
            .where(Price.effective_to.is_(None))
        )
        if current_price is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Menu item {item_id} has no current price; set one first",
            )
        db.add(
            MenuItemInMenu(
                menu_id=menu.id,
                menu_item_id=item_id,
                price_id=current_price.id,
            )
        )

    db.commit()
    db.refresh(menu)
    return MenuRead.model_validate(menu)


@router.post(
    "/{menu_id}/archive",
    response_model=MenuRead,
    summary="Archive a menu (admin)",
)
def archive_menu(
    menu_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> MenuRead:
    """Mark a menu as archived. Terminal — archival cannot be undone."""
    menu = db.get(Menu, menu_id)
    if menu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu not found")
    if menu.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Menu is already archived")
    menu.archived_at = datetime.now(UTC)
    db.commit()
    db.refresh(menu)
    return MenuRead.model_validate(menu)
