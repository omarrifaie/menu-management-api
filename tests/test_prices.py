"""Price endpoint tests — RBAC + supersession semantics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models.category import Category
from app.models.menu_item import MenuItem
from app.models.price import Price
from app.models.user import User, UserRole


def _create_item(
    client: TestClient, admin_token: str, auth_header, name: str = "Burger"
) -> int:
    cat = client.post(
        "/categories",
        json={"name": "Mains"},
        headers=auth_header(admin_token),
    )
    if cat.status_code == 409:  # category already exists from a previous call in this test
        cat_id = client.get("/categories").json()[0]["id"]
    else:
        cat_id = cat.json()["id"]

    resp = client.post(
        "/menu-items",
        json={"category_id": cat_id, "name": name},
        headers=auth_header(admin_token),
    )
    return resp.json()["id"]


def test_staff_cannot_post_price(
    client: TestClient, admin_token, staff_token, auth_header
) -> None:
    item_id = _create_item(client, admin_token, auth_header)
    resp = client.post(
        f"/menu-items/{item_id}/prices",
        json={"amount_cents": 1200},
        headers=auth_header(staff_token),
    )
    assert resp.status_code == 403


def test_admin_price_supersession(
    client: TestClient, admin_token, auth_header
) -> None:
    item_id = _create_item(client, admin_token, auth_header)

    r1 = client.post(
        f"/menu-items/{item_id}/prices",
        json={"amount_cents": 1000},
        headers=auth_header(admin_token),
    )
    assert r1.status_code == 201
    first = r1.json()
    assert first["effective_to"] is None

    r2 = client.post(
        f"/menu-items/{item_id}/prices",
        json={"amount_cents": 1250},
        headers=auth_header(admin_token),
    )
    assert r2.status_code == 201
    second = r2.json()
    assert second["effective_to"] is None

    history = client.get(f"/menu-items/{item_id}/prices").json()
    assert len(history) == 2
    # Most recent first
    assert history[0]["amount_cents"] == 1250
    assert history[0]["effective_to"] is None
    assert history[1]["amount_cents"] == 1000
    assert history[1]["effective_to"] is not None  # got closed off

    item = client.get(f"/menu-items/{item_id}").json()
    assert item["current_price_cents"] == 1250


def test_price_history_is_public(client: TestClient, admin_token, auth_header) -> None:
    item_id = _create_item(client, admin_token, auth_header)
    client.post(
        f"/menu-items/{item_id}/prices",
        json={"amount_cents": 500},
        headers=auth_header(admin_token),
    )
    resp = client.get(f"/menu-items/{item_id}/prices")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_db_rejects_two_open_prices_for_same_item(db) -> None:
    """The partial unique index forbids two open price rows for one item.

    True concurrent inserts are awkward to simulate against in-memory
    SQLite (the test fixtures share a single underlying connection via
    ``StaticPool``), so we exercise the invariant directly: insert two
    rows with ``effective_to IS NULL`` for the same menu item and confirm
    the second one fails the unique constraint. This is exactly the
    state two concurrent writers would race into, just without the race.
    """
    admin = User(email="a@x.com", hashed_password="x", role=UserRole.ADMIN)
    db.add(admin)
    db.flush()
    cat = Category(name="C")
    db.add(cat)
    db.flush()
    item = MenuItem(category_id=cat.id, name="Burger")
    db.add(item)
    db.flush()

    now = datetime.now(UTC)
    db.add(
        Price(
            menu_item_id=item.id,
            amount_cents=1000,
            effective_from=now,
            effective_to=None,
            created_by=admin.id,
        )
    )
    db.flush()

    db.add(
        Price(
            menu_item_id=item.id,
            amount_cents=1100,
            effective_from=now,
            effective_to=None,
            created_by=admin.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
