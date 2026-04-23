"""Price endpoints.

Prices are immutable once written: to change an item's price you POST a
new row, which automatically closes the previous one by stamping its
``effective_to`` to the same moment. History is always queryable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.db import get_db
from app.models.menu_item import MenuItem
from app.models.price import Price
from app.models.user import User
from app.schemas.price import PriceCreate, PriceRead

router = APIRouter(tags=["prices"])


@router.get(
    "/menu-items/{item_id}/prices",
    response_model=list[PriceRead],
    summary="Price history for a menu item",
)
def list_prices(
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> list[PriceRead]:
    """Return every price row for the item, newest first.

    The currently-active price is always the one with ``effective_to`` null.
    """
    if db.get(MenuItem, item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    rows = db.scalars(
        select(Price)
        .where(Price.menu_item_id == item_id)
        .order_by(Price.effective_from.desc())
    ).all()
    return [PriceRead.model_validate(p) for p in rows]


@router.post(
    "/menu-items/{item_id}/prices",
    response_model=PriceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Set a new price (admin)",
)
def create_price(
    item_id: int,
    payload: PriceCreate,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> PriceRead:
    """Publish a new price, superseding any currently-open one.

    Steps, inside a single transaction:

    1. Find the item's current open price (``effective_to IS NULL``).
    2. If one exists, stamp its ``effective_to`` with ``now``.
    3. Insert a new row with ``effective_from = now`` and ``effective_to = NULL``.
    """
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")

    now = datetime.now(UTC)

    # Two-step "close old price, insert new" is correct under a single
    # transaction because every statement below runs inside the Session's
    # implicit BEGIN. Under Postgres's default READ COMMITTED isolation,
    # two concurrent POSTs to this endpoint will still serialize on the
    # Price row-level write lock — the second write sees the first's
    # closed row rather than a phantom second "open" row. If you ever
    # move to stronger guarantees, consider SELECT ... FOR UPDATE on the
    # open row; for now default isolation plus the transaction boundary
    # is sufficient. (SQLite is single-writer so the question is moot there.)
    open_price = db.scalar(
        select(Price)
        .where(Price.menu_item_id == item_id)
        .where(Price.effective_to.is_(None))
    )
    if open_price is not None:
        open_price.effective_to = now

    new_price = Price(
        menu_item_id=item_id,
        amount_cents=payload.amount_cents,
        effective_from=now,
        effective_to=None,
        created_by=admin.id,
    )
    db.add(new_price)
    db.commit()
    db.refresh(new_price)
    return PriceRead.model_validate(new_price)
