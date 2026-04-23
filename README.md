# Menu Management API

A FastAPI REST service for managing restaurant menus — categories, menu
items, prices, and versioned menu snapshots — with role-based JWT auth
and an OpenAPI-documented surface. Built as a portfolio project.

**Stack:** Python 3.11 · FastAPI · SQLAlchemy 2 · Pydantic v2 · Alembic ·
python-jose · passlib · pytest. Production target is PostgreSQL; SQLite
is supported out of the box for zero-setup demos.

---

## Features

- **Full CRUD across three resource types** — categories, menu items,
  and prices — with a fourth "versioned menu" resource built on top.
- **Versioned menu archives.** Publishing a menu snapshots the current
  items and their current prices into a join table. Prices can change
  afterward without altering archived menus; historical versions remain
  faithful to what customers originally saw. *Only price is frozen* —
  an item's `name`, `description`, and `prep_time_minutes` are read
  live from the item table when a menu is rendered, so later edits to
  those fields are reflected in previously-archived menus. The
  commercial fact (what a customer paid) is preserved; cosmetic fields
  track the live item.
- **Daily specials** are first-class via a boolean flag on menu items
  and a `?daily_specials_only=true` filter on the list endpoint.
- **Role-based JWT auth.** Two roles: `admin` (does everything) and
  `staff` (reads everything, may create new menu items). Price changes,
  item edits, and menu archival are admin-only.
- **Normalized schema.** Prices live in their own table keyed by item
  with `effective_from` / `effective_to`, so history is preserved
  without duplicating it onto items or menus. A menu snapshot points at
  a specific `price_id` rather than copying the amount.
- **OpenAPI/Swagger** at `/docs` and `/redoc` — title, tags, and per-
  route descriptions are all curated rather than auto-inferred.

---

## Architecture

```
                    ┌──────────────────────────────┐
                    │        FastAPI app           │
                    │  /docs · /redoc · /health    │
                    └──────────────┬───────────────┘
                                   │
       ┌───────────┬───────────────┼────────────┬──────────────┐
       │           │               │            │              │
 ┌───────────┐ ┌──────────┐ ┌─────────────┐ ┌─────────┐  ┌───────────┐
 │  /auth    │ │/categories│ │/menu-items  │ │ /prices │  │  /menus   │
 │ register  │ │   CRUD   │ │  + filters  │ │ history │  │  publish  │
 │  login    │ │          │ │             │ │ set new │  │  archive  │
 │  /me      │ │          │ │             │ │         │  │  /items   │
 └─────┬─────┘ └────┬─────┘ └──────┬──────┘ └────┬────┘  └─────┬─────┘
       │            │              │             │             │
       ▼            ▼              ▼             ▼             ▼
   ┌──────────────────────────────────────────────────────────────┐
   │     JWT dependency · require_role(admin|staff) guards        │
   └──────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
            ┌──────────────────────────────────┐
            │        SQLAlchemy 2.x ORM        │
            └──────────────┬───────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
  ┌────────────┐   PRODUCTION            ┌────────────┐
  │ PostgreSQL │◀───────────────────────▶│   SQLite   │   LOCAL DEMO
  └────────────┘                         └────────────┘
```

Data model (entities, PK → relationships):

```
User ─── created ───▶ Price ─── for ───▶ MenuItem ─── in ───▶ Category
                        ▲                      ▲
                        │                      │
                        └── snapshot row ──────┤
                                               │
                                          MenuItemInMenu ──▶ Menu
                                              (composite PK)
```

---

## Running locally

```bash
# 1. Create a virtualenv and install deps
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Copy environment defaults
cp .env.example .env                # edit JWT_SECRET before anything real

# 3. Apply the initial migration to a fresh SQLite DB
alembic upgrade head

# 4. Seed demo data (admin + staff user, categories, items, a published menu)
python -m scripts.seed

# 5. Serve
uvicorn app.main:app --reload
```

Then open **http://localhost:8000/docs** and authorize with the
credentials printed by the seed script.

### Switching to PostgreSQL

One environment variable — no code changes:

```bash
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/menu"
pip install -e ".[postgres]"
alembic upgrade head
```

---

## API overview

| Method | Path                              | Auth      | What it does                             |
|--------|-----------------------------------|-----------|------------------------------------------|
| POST   | `/auth/register`                  | see below | Register a new user                      |
| POST   | `/auth/login`                     | public    | Exchange credentials for a JWT           |
| GET    | `/auth/me`                        | any user  | Return the current user                  |
| GET    | `/categories`                     | public    | List categories                          |
| POST   | `/categories`                     | admin     | Create category                          |
| PATCH  | `/categories/{id}`                | admin     | Update category                          |
| DELETE | `/categories/{id}`                | admin     | Delete (blocked if active items exist)   |
| GET    | `/menu-items`                     | public    | List items (filters: category / specials)|
| GET    | `/menu-items/{id}`                | public    | Fetch one item + its current price       |
| POST   | `/menu-items`                     | staff     | Create a menu item                       |
| PATCH  | `/menu-items/{id}`                | admin     | Edit a menu item                         |
| DELETE | `/menu-items/{id}`                | admin     | Delete (blocked if referenced by a menu) |
| GET    | `/menu-items/{id}/prices`         | public    | Price history for an item                |
| POST   | `/menu-items/{id}/prices`         | admin     | Set a new price (supersedes the old one) |
| GET    | `/menus`                          | public    | List menus (active + archived)           |
| GET    | `/menus/{id}`                     | public    | Fetch one menu                           |
| GET    | `/menus/{id}/items`               | public    | Frozen items + prices for a menu version |
| POST   | `/menus`                          | admin     | Publish a new menu version               |
| POST   | `/menus/{id}/archive`             | admin     | Archive a menu (terminal)                |

`/auth/register` is open when `DEV_ALLOW_OPEN_REGISTRATION=true` (dev
default) and admin-only otherwise.

---

## Authentication flow

```
┌──────┐                       ┌───────────────┐
│Client│                       │ /auth/login   │
└───┬──┘                       └───────┬───────┘
    │  POST {email, password}          │
    │ ────────────────────────────────▶│
    │                                  │  verify bcrypt hash
    │                                  │  mint HS256 JWT
    │  { access_token, expires_in }    │
    │ ◀────────────────────────────────│
    │
    │  subsequent requests carry:
    │  Authorization: Bearer <token>
    │
    │                         ┌────────────────────────┐
    │                         │ get_current_user       │
    │ ───────protected───────▶│  decode + verify JWT   │
    │                         │  SELECT user by sub    │
    │                         │                        │
    │                         │ require_role(...)      │
    │                         │  admin ⊇ staff         │
    │                         └────────────────────────┘
```

Token payload: `{sub: user_id, role: "admin" | "staff", iat, exp}`.
Default expiry is 60 minutes; override with `JWT_EXPIRE_MINUTES`.

---

## Running tests

```bash
pytest                          # run the suite
pytest --cov=src/app            # with coverage
```

The test suite covers auth happy path + credential failures + expired
tokens, RBAC on every mutating endpoint, price supersession, and the
core archival-fidelity guarantee - changing a price after archiving a
menu does not alter what the archived menu returns.

---

## Project layout

```
src/app/
├── main.py               FastAPI factory, OpenAPI metadata
├── config.py             pydantic-settings
├── db.py                 engine, SessionLocal, get_db
├── auth/                 passwords, JWT, dependencies, /auth router
├── models/               SQLAlchemy 2.x declarative models
├── schemas/              Pydantic v2 request/response schemas
└── routers/              /categories /menu-items /prices /menus
alembic/                  migration env + initial schema revision
scripts/seed.py           demo data bootstrap
tests/                    pytest + in-memory SQLite fixtures
```

---

## What's next

Things I'd build if this were more than a portfolio piece:

- **Orders + tickets.** The data model already supports "which item and
  which price" - adding an Order table would close the loop from menu
  to kitchen.
- **Soft-deleted menu items** should probably keep their price history
  accessible through a dedicated endpoint rather than just disappearing
  from `?include_inactive=false` responses.
- **Image uploads** for items, persisted to object storage with signed
  URLs served through the item response.
- **Per-tenant isolation.** A `restaurant_id` column on every table
  plus a middleware that scopes reads/writes to the caller's tenant.
- **Event log.** Right now archival and price changes are inferable
  from row states but not auditable - an append-only events table
  keyed by actor would fix that.
- **Caching.** `GET /menus/{id}/items` is immutable once its menu is
  archived; it's an obvious candidate for aggressive HTTP caching.


Built by Omar Rifaie - [github.com/omarrifaie](https://github.com/omarrifaie) · [linkedin.com/in/omar-rifaie-](https://linkedin.com/in/omar-rifaie-)
