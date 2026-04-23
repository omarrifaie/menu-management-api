"""FastAPI application factory + router wiring.

Importing ``app`` directly gives uvicorn a target to serve:

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.auth.router import router as auth_router
from app.routers.categories import router as categories_router
from app.routers.menu_items import router as menu_items_router
from app.routers.menus import router as menus_router
from app.routers.prices import router as prices_router

TAG_METADATA = [
    {
        "name": "auth",
        "description": (
            "Register users and exchange credentials for a JWT. Tokens are "
            "HS256-signed and carry `sub` (user id) and `role` claims."
        ),
    },
    {
        "name": "categories",
        "description": (
            "Top-level groupings for menu items. Read-only for the public; "
            "admin-only for writes."
        ),
    },
    {
        "name": "menu-items",
        "description": (
            "The individual dishes, drinks, and specials. Staff may create new "
            "items; only admins may edit or remove them."
        ),
    },
    {
        "name": "prices",
        "description": (
            "Append-only price history for each menu item. Posting a new price "
            "automatically closes the previous row."
        ),
    },
    {
        "name": "menus",
        "description": (
            "Versioned menu snapshots. Publishing freezes each item's current "
            "price, so archived menus render faithfully forever."
        ),
    },
]


API_DESCRIPTION = """
A REST service for managing restaurant menus — built as a portfolio project.

**Feature highlights**

* Normalized schema: items, categories, and prices each live in their own
  table, so historical prices are preserved without duplication.
* Versioned menus: each published menu snapshots the exact items and
  prices that were current at publish time. Prices can evolve after
  publication without retroactively altering archived menus.
* Role-based access control: every mutating endpoint checks a JWT. Staff
  can expand the menu; only admins may adjust prices or archive menus.

The production target is PostgreSQL, but the project runs against SQLite
by default for zero-setup demos — switch by setting the `DATABASE_URL`
environment variable.
"""


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Separating this into a factory makes test fixtures simpler — they can
    construct their own app bound to an in-memory database.
    """
    app = FastAPI(
        title="Menu Management API",
        version=__version__,
        summary="Restaurant menu CRUD with JWT auth and versioned menu archives.",
        description=API_DESCRIPTION,
        openapi_tags=TAG_METADATA,
        contact={"name": "Omar Rifaie"},
        license_info={"name": "MIT", "identifier": "MIT"},
    )

    app.include_router(auth_router)
    app.include_router(categories_router)
    app.include_router(menu_items_router)
    app.include_router(prices_router)
    app.include_router(menus_router)

    @app.get("/health", tags=["system"], summary="Liveness probe")
    def health() -> dict[str, str]:
        """Lightweight health check that does not touch the database."""
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
