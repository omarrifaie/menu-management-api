"""Category CRUD tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_categories_is_public(client: TestClient) -> None:
    resp = client.get("/categories")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_category_requires_admin(client: TestClient, staff_token, auth_header) -> None:
    resp = client.post(
        "/categories",
        json={"name": "Mains"},
        headers=auth_header(staff_token),
    )
    assert resp.status_code == 403


def test_admin_full_lifecycle(client: TestClient, admin_token, auth_header) -> None:
    resp = client.post(
        "/categories",
        json={"name": "Drinks", "display_order": 1},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    cat = resp.json()
    cat_id = cat["id"]

    resp = client.patch(
        f"/categories/{cat_id}",
        json={"display_order": 5},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["display_order"] == 5

    resp = client.delete(f"/categories/{cat_id}", headers=auth_header(admin_token))
    assert resp.status_code == 204

    resp = client.get("/categories")
    assert resp.json() == []


def test_duplicate_category_name_rejected(client: TestClient, admin_token, auth_header) -> None:
    client.post("/categories", json={"name": "Desserts"}, headers=auth_header(admin_token))
    resp = client.post(
        "/categories", json={"name": "Desserts"}, headers=auth_header(admin_token)
    )
    assert resp.status_code == 409
