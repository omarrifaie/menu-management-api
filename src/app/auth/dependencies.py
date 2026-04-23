"""FastAPI dependencies for authentication and role-based access control."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.jwt import TokenError, decode_access_token
from app.config import Settings, get_settings
from app.db import get_db
from app.models.user import User, UserRole

# The tokenUrl is purely informational for Swagger; our real login endpoint
# is /auth/login and accepts JSON rather than form-encoded data.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_user(
    token: str | None,
    db: Session,
    settings: Settings,
) -> User | None:
    """Shared token → user lookup. Returns None only when ``token`` is None."""
    if token is None:
        return None

    try:
        payload = decode_access_token(token, settings=settings)
    except TokenError as exc:
        raise _unauthorized(f"Invalid token: {exc}") from exc

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise _unauthorized("Invalid token subject") from exc

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("User no longer exists")
    return user


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Resolve the authenticated :class:`User`, or raise HTTP 401.

    Injects the Bearer token from the ``Authorization`` header, validates
    it, and loads the referenced user. This is the dependency every
    protected endpoint should use.
    """
    user = _resolve_user(token, db, settings)
    if user is None:
        raise _unauthorized("Not authenticated")
    return user


def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User | None:
    """Like :func:`get_current_user` but returns None when no token is sent.

    An *invalid* token (bad signature, expired, unknown user) still raises
    401 — silent fallback would mask real authentication problems.
    """
    return _resolve_user(token, db, settings)


def require_role(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Build a dependency that enforces role membership.

    Admins always pass — they implicitly have every staff permission.

    Usage::

        @router.post(..., dependencies=[Depends(require_role(UserRole.ADMIN))])
    """

    def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role == UserRole.ADMIN:
            return user
        if user.role in allowed_roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {[r.value for r in allowed_roles]}",
        )

    return _dep


# Convenience aliases for the two most common cases.
require_admin = require_role(UserRole.ADMIN)
require_staff = require_role(UserRole.STAFF, UserRole.ADMIN)
