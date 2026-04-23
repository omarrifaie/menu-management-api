# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-04-23

### Added
- Initial public release of the Menu Management API.
- Full CRUD for the three core resource types: categories, menu items, and
  prices, backed by a normalized PostgreSQL schema (SQLite supported for
  local development).
- Versioned menu snapshots (`MenuItemInMenu`) so archived menus render with
  the exact items and prices that were in effect on their publication date.
- Price history retained per menu item, with the "current" price identified
  by a null `effective_to`.
- Role-based JWT authentication (HS256) with `admin` and `staff` roles,
  enforced on every mutating endpoint.
- OpenAPI/Swagger documentation auto-generated at `/docs` and `/redoc`,
  with customized metadata and per-route descriptions.
- Alembic migration covering the full initial schema.
- Seed script (`scripts/seed.py`) that provisions demo users, categories,
  items, prices, and one published menu.
- Pytest suite covering auth flows, RBAC, price supersession, and menu
  snapshot fidelity across archival.
