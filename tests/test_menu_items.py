"""Menu item CRUD + RBAC tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _make_category(client: TestClient, admin_token: str, auth_header) -> int:
    resp = client.post(
        "/categories",
        json={"name": "Mains"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_staff_can_create_item(
    client: TestClient, admin_token, staff_token, auth_header
) -> None:
    cat_id = _make_category(client, admin_token, auth_header)
    resp = client.post(
        "/menu-items",
        json={"category_id": cat_id, "name": "Burger", "prep_time_minutes": 12},
        headers=auth_header(staff_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Burger"
    assert body["current_price_cents"] is None  # no price set yet


def test_staff_cannot_patch_item(
    client: TestClient, admin_token, staff_token, auth_header
) -> None:
    cat_id = _make_category(client, admin_token, auth_header)
    resp = client.post(
        "/menu-items",
        json={"category_id": cat_id, "name": "Fries"},
        headers=auth_header(admin_token),
    )
    item_id = resp.json()["id"]

    resp = client.patch(
        f"/menu-items/{item_id}",
        json={"name": "Truffle Fries"},
        headers=auth_header(staff_token),
    )
    assert resp.status_code == 403


def test_admin_can_patch_and_delete(
    client: TestClient, admin_token, auth_header
) -> None:
    cat_id = _make_category(client, admin_token, auth_header)
    resp = client.post(
        "/menu-items",
        json={"category_id": cat_id, "name": "Salad"},
        headers=auth_header(admin_token),
    )
    item_id = resp.json()["id"]

    resp = client.patch(
        f"/menu-items/{item_id}",
        json={"is_daily_special": True},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_daily_special"] is True

    resp = client.delete(f"/menu-items/{item_id}", headers=auth_header(admin_token))
    assert resp.status_code == 204


def test_list_filters(client: TestClient, admin_token, auth_header) -> None:
    cat_id = _make_category(client, admin_token, auth_header)
    client.post(
        "/menu-items",
        json={"category_id": cat_id, "name": "Regular"},
        headers=auth_header(admin_token),
    )
    client.post(
        "/menu-items",
        json={
            "category_id": cat_id,
            "name": "Special",
            "is_daily_special": True,
        },
        headers=auth_header(admin_token),
    )

    all_items = client.get("/menu-items").json()
    assert {i["name"] for i in all_items} == {"Regular", "Special"}

    specials = client.get("/menu-items?daily_specials_only=true").json()
    assert {i["name"] for i in specials} == {"Special"}
