"""JWT encode/decode helpers.

All tokens use HS256 with a secret configured via ``JWT_SECRET``. The
payload carries:

* ``sub``  — the user id as a string
* ``role`` — either ``admin`` or ``staff``
* ``exp``  — standard expiry claim
* ``iat``  — issued-at
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.config import Settings


class TokenError(Exception):
    """Raised when a supplied token is invalid, expired, or malformed."""


def create_access_token(*, user_id: int, role: str, settings: Settings) -> tuple[str, int]:
    """Create a signed JWT.

    Returns a ``(token, expires_in_seconds)`` pair so callers can surface
    the expiry to the client without re-decoding the token.
    """
    expires_in = settings.jwt_expire_minutes * 60
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str, *, settings: Settings) -> dict[str, Any]:
    """Decode and validate a JWT, returning the payload dict.

    Raises :class:`TokenError` on any failure (invalid signature, expired
    token, missing required claim). Callers should catch this and return
    HTTP 401.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc

    if "sub" not in payload or "role" not in payload:
        raise TokenError("token payload missing required claims")
    return payload
