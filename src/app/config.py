"""
Application configuration.

Values are read from environment variables (and optionally a ``.env`` file
at the project root). See ``.env.example`` for the full list.

The single source of truth is the :class:`Settings` instance exposed via
:func:`get_settings`. Importing it in a router or service keeps tests
trivial — ``app.dependency_overrides`` can replace the dependency without
touching module-level state.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-only-secret-do-not-use-in-production"

# Strings that ship in this repository (the in-code default plus the
# placeholder in .env.example) and so are effectively public. A non-SQLite
# deployment that boots with any of these would let anyone mint admin
# tokens. The list catches the secrets we know about; the 32-char minimum
# (enforced separately) catches anything we haven't anticipated.
KNOWN_INSECURE_JWT_SECRETS = frozenset(
    {
        DEFAULT_JWT_SECRET,
        "change-me-to-a-long-random-string",
    }
)
MIN_PRODUCTION_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Strongly-typed view of the process environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Database ----------------------------------------------------------
    # SQLite is the default so the project runs on a laptop with zero setup.
    # Production deployments should point this at PostgreSQL.
    database_url: str = Field(default="sqlite:///./menu.db")

    # ---- JWT --------------------------------------------------------------
    jwt_secret: str = Field(default=DEFAULT_JWT_SECRET)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expire_minutes: int = 60

    # ---- Feature flags ----------------------------------------------------
    dev_allow_open_registration: bool = False

    # ---- Uvicorn ----------------------------------------------------------
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False

    @property
    def is_sqlite(self) -> bool:
        """True when the current database URL points at SQLite."""
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Cached so ``.env`` is only parsed once per process. Tests that need
    different settings should call ``get_settings.cache_clear()`` or use
    FastAPI's ``dependency_overrides``.
    """
    return Settings()
