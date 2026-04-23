"""Auth endpoint tests — register, login, expired / invalid tokens, /me."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt


def test_register_and_login_happy_path(client: TestClient) -> None:
    resp = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123", "role": "staff"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "user@example.com"
    assert body["role"] == "staff"
    assert "id" in body

    resp = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    token_body = resp.json()
    assert token_body["token_type"] == "bearer"
    assert token_body["expires_in"] > 0
    assert token_body["access_token"]


def test_login_rejects_wrong_password(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "u@example.com", "password": "correcthorse", "role": "staff"},
    )
    resp = client.post(
        "/auth/login",
        json={"email": "u@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_login_rejects_unknown_email(client: TestClient) -> None:
    resp = client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "whatever12"},
    )
    assert resp.status_code == 401


def test_duplicate_registration_returns_409(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "password123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_expired_token_is_rejected(client: TestClient, settings, admin_token, auth_header) -> None:
    """A manually-minted JWT with ``exp`` in the past must be rejected as 401."""
    # Seed a user so the token's `sub` resolves — we need the id. Use the
    # admin that admin_token already created.
    me = client.get("/auth/me", headers=auth_header(admin_token))
    assert me.status_code == 200
    user_id = me.json()["id"]

    expired_payload = {
        "sub": str(user_id),
        "role": "admin",
        "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(
        expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


def test_invalid_signature_rejected(client: TestClient, admin_token) -> None:
    resp = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert resp.status_code == 401


def test_me_returns_current_user(client: TestClient, admin_token, auth_header) -> None:
    resp = client.get("/auth/me", headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@example.com"
    assert resp.json()["role"] == "admin"


def test_closed_registration_requires_admin(app, staff_token, auth_header) -> None:
    """With open registration off, only admins can register new users."""
    from app.config import Settings, get_settings

    # Flip the flag by overriding the dependency for this test only.
    closed = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-for-unit-tests-only",
        dev_allow_open_registration=False,
    )
    app.dependency_overrides[get_settings] = lambda: closed

    # Reuse a test client bound to this reconfigured app.
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        anon = c.post(
            "/auth/register",
            json={"email": "anon@example.com", "password": "password123"},
        )
        assert anon.status_code == 403

        as_staff = c.post(
            "/auth/register",
            headers=auth_header(staff_token),
            json={"email": "anon2@example.com", "password": "password123"},
        )
        assert as_staff.status_code == 403
