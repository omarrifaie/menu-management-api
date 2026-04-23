"""Declarative base + shared type aliases for all ORM models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp.

    Used as the default for ``created_at`` / ``effective_from`` columns. We
    avoid :func:`datetime.utcnow` because it returns a naive timestamp.
    """
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base that every ORM model inherits from."""
