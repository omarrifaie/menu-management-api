"""
Database engine, session factory, and FastAPI dependency.

The engine is built lazily so test fixtures can override the database URL
before the first session is created.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.base import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _build_engine(url: str) -> Engine:
    """Create a SQLAlchemy engine with settings appropriate for the URL."""
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        # SQLite's default check_same_thread guard fights FastAPI's threaded
        # request handling. Disabling it is safe because each request gets
        # its own Session via the get_db() dependency.
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args, future=True)


def get_engine() -> Engine:
    """Return the process-wide engine, building it on first call."""
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings().database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional SQLAlchemy session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_engine_for_tests(url: str) -> None:
    """Rebuild the engine against a different URL (test fixtures only)."""
    global _engine, _SessionLocal
    _engine = _build_engine(url)
    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


__all__ = ["Base", "get_db", "get_engine", "get_session_factory", "reset_engine_for_tests"]
