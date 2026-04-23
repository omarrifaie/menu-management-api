"""Shared pytest fixtures.

Each test gets a freshly-created in-memory SQLite database. We use a
``StaticPool`` so every session produced by the override lands in the
same underlying SQLite connection — otherwise each session would see a
different empty ``:memory:``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import get_db
from app.main import create_app
from app.models.base import Base


@pytest.fixture()
def settings() -> Settings:
    """Test-flavored settings: open registration, short-but-valid JWT expiry."""
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret="test-secret-for-unit-tests-only",
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
        dev_allow_open_registration=True,
    )


@pytest.fixture()
def engine():
    """In-memory SQLite engine with FK enforcement enabled."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    # SQLite disables FKs by default; opt in so our ON DELETE rules apply.
    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_connection, _):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


@pytest.fixture()
def db(session_factory) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app(session_factory, settings: Settings) -> FastAPI:
    """FastAPI instance with DB + settings overridden for the test DB."""
    application = create_app()

    def _get_db_override() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = _get_db_override
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Convenience helpers used by multiple test modules
# ---------------------------------------------------------------------------


@pytest.fixture()
def register_and_login(client: TestClient):
    """Factory fixture that returns a helper to register + login a user.

    Usage in a test::

        token = register_and_login("a@x.com", "pw12345678", role="admin")
    """

    def _do(email: str, password: str, role: str = "staff") -> str:
        resp = client.post(
            "/auth/register",
            json={"email": email, "password": password, "role": role},
        )
        assert resp.status_code == 201, resp.text
        resp = client.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _do


@pytest.fixture()
def admin_token(register_and_login) -> str:
    return register_and_login("admin@example.com", "adminpass123", role="admin")


@pytest.fixture()
def staff_token(register_and_login) -> str:
    return register_and_login("staff@example.com", "staffpass123", role="staff")


@pytest.fixture()
def auth_header():
    def _header(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _header
