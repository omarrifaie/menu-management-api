"""Menu publication + snapshot fidelity tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_item_with_price(
    client: TestClient, admin_token: str, auth_header, *, amount_cents: int, name: str
) -> int:
    cats = client.get("/categories").json()
    if not cats:
        cat_id = client.post(
            "/categories", json={"name": "Mains"}, headers=auth_header(admin_token)
        ).json()["id"]
    else:
        cat_id = cats[0]["id"]

    item = client.post(
        "/menu-items",
        json={"category_id": cat_id, "name": name},
        headers=auth_header(admin_token),
    ).json()
    client.post(
        f"/menu-items/{item['id']}/prices",
        json={"amount_cents": amount_cents},
        headers=auth_header(admin_token),
    )
    return item["id"]


def test_publish_menu_snapshots_current_prices(
    client: TestClient, admin_token, auth_header
) -> None:
    id_a = _seed_item_with_price(client, admin_token, auth_header, amount_cents=800, name="A")
    id_b = _seed_item_with_price(client, admin_token, auth_header, amount_cents=1500, name="B")

    resp = client.post(
        "/menus",
        json={"name": "Dinner", "item_ids": [id_a, id_b]},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    menu = resp.json()
    assert menu["version"] == 1
    assert menu["archived_at"] is None

    entries = client.get(f"/menus/{menu['id']}/items").json()
    priced = {e["name"]: e["amount_cents"] for e in entries}
    assert priced == {"A": 800, "B": 1500}


def test_menu_version_increments(client: TestClient, admin_token, auth_header) -> None:
    id_a = _seed_item_with_price(client, admin_token, auth_header, amount_cents=900, name="X")
    r1 = client.post(
        "/menus",
        json={"name": "Lunch", "item_ids": [id_a]},
        headers=auth_header(admin_token),
    )
    r2 = client.post(
        "/menus",
        json={"name": "Lunch", "item_ids": [id_a]},
        headers=auth_header(admin_token),
    )
    assert r1.json()["version"] == 1
    assert r2.json()["version"] == 2


def test_archived_menu_keeps_original_prices_after_repricing(
    client: TestClient, admin_token, auth_header
) -> None:
    """The core claim of the project: archived menus are frozen."""
    id_a = _seed_item_with_price(
        client, admin_token, auth_header, amount_cents=1000, name="Pasta"
    )

    # Publish at 1000¢.
    menu = client.post(
        "/menus",
        json={"name": "Autumn", "item_ids": [id_a]},
        headers=auth_header(admin_token),
    ).json()
    menu_id = menu["id"]

    # Archive it.
    resp = client.post(f"/menus/{menu_id}/archive", headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert resp.json()["archived_at"] is not None

    # Price changes afterward.
    client.post(
        f"/menu-items/{id_a}/prices",
        json={"amount_cents": 1800},
        headers=auth_header(admin_token),
    )
    assert client.get(f"/menu-items/{id_a}").json()["current_price_cents"] == 1800

    # But the archived menu still quotes the original price.
    entries = client.get(f"/menus/{menu_id}/items").json()
    assert entries[0]["amount_cents"] == 1000


def test_archive_requires_admin(client: TestClient, admin_token, staff_token, auth_header) -> None:
    id_a = _seed_item_with_price(client, admin_token, auth_header, amount_cents=500, name="Z")
    menu = client.post(
        "/menus",
        json={"name": "Test", "item_ids": [id_a]},
        headers=auth_header(admin_token),
    ).json()
    resp = client.post(f"/menus/{menu['id']}/archive", headers=auth_header(staff_token))
    assert resp.status_code == 403


def test_cannot_archive_twice(client: TestClient, admin_token, auth_header) -> None:
    id_a = _seed_item_with_price(client, admin_token, auth_header, amount_cents=400, name="Q")
    menu = client.post(
        "/menus",
        json={"name": "Brunch", "item_ids": [id_a]},
        headers=auth_header(admin_token),
    ).json()
    r1 = client.post(f"/menus/{menu['id']}/archive", headers=auth_header(admin_token))
    r2 = client.post(f"/menus/{menu['id']}/archive", headers=auth_header(admin_token))
    assert r1.status_code == 200
    assert r2.status_code == 409


def test_publish_rejects_items_without_price(
    client: TestClient, admin_token, auth_header
) -> None:
    cat_id = client.post(
        "/categories", json={"name": "Bev"}, headers=auth_header(admin_token)
    ).json()["id"]
    no_price = client.post(
        "/menu-items",
        json={"category_id": cat_id, "name": "Water"},
        headers=auth_header(admin_token),
    ).json()
    resp = client.post(
        "/menus",
        json={"name": "Any", "item_ids": [no_price["id"]]},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422
