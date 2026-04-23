"""Price endpoint tests — RBAC + supersession semantics."""

from __future__ import annotations

from fastapi.testclient import TestClient


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
