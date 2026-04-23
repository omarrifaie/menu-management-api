"""Auth-related request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    """Payload for ``POST /auth/register``."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.STAFF


class LoginRequest(BaseModel):
    """Payload for ``POST /auth/login``."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT bearer token wrapper."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the token expires
