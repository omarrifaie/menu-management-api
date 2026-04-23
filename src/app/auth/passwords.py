"""Password hashing using bcrypt (via passlib).

Keeping the hashing logic in its own module means the algorithm can evolve
without touching routes or the user model.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the supplied plaintext password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison via passlib."""
    return _pwd_context.verify(plain, hashed)
