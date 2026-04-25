"""``/auth`` endpoints: register + login."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_optional_user
from app.auth.jwt import create_access_token
from app.auth.passwords import hash_password, verify_password
from app.config import Settings, get_settings
from app.db import get_db
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[User | None, Depends(get_optional_user)] = None,
) -> UserRead:
    """Create a new user account.

    Access rules:

    * If ``DEV_ALLOW_OPEN_REGISTRATION`` is **true**, anyone may register
      an account with any role. This is intended for local demos only.
    * Otherwise, the caller must present a valid admin JWT — admins
      provision all users in production.

    Status code note: when registration is restricted, **anonymous**
    callers get a **403** (authenticated but lacking the admin role is
    the same shape as "no auth at all" for this route — there is no
    legitimate unauthenticated path). Callers presenting an **expired
    or otherwise invalid** JWT get a **401** from the token dependency
    before this handler runs. This asymmetry is intentional: 401 tells
    the client to refresh its token, 403 tells it the answer won't
    change without different credentials.
    """
    if not settings.dev_allow_open_registration:
        # Hand-rolled auth check so we can give a clean 403 rather than
        # forcing every registration call through a role Depends() that
        # would 401 when open registration is on.
        if current_user is None or current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration is restricted to admins",
            )

    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange credentials for a JWT",
)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Validate credentials and return a signed JWT.

    A single generic 401 is returned for every credential failure to
    avoid leaking whether an email exists in the database.
    """
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires_in = create_access_token(
        user_id=user.id, role=user.role.value, settings=settings
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserRead, summary="Return the current user")
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    """Introspection endpoint — useful for client apps verifying their token."""
    return UserRead.model_validate(current_user)
