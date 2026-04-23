"""Populate the database with a demo dataset.

Run from the project root::

    python -m scripts.seed            # seed into existing tables
    python -m scripts.seed --reset    # drop everything, recreate tables, seed

The script relies on Alembic to create the schema — run ``alembic upgrade
head`` first. If the ``users`` table is missing we bail out with a
pointer to the migration command. If the admin email already exists the
script exits cleanly; pass ``--reset`` to wipe and reseed.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

# Allow running as `python scripts/seed.py` in addition to `python -m scripts.seed`.
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sqlalchemy import inspect, select  # noqa: E402

from app.auth.passwords import hash_password  # noqa: E402
from app.db import get_engine, get_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Category,
    Menu,
    MenuItem,
    MenuItemInMenu,
    Price,
    User,
    UserRole,
)

ADMIN_EMAIL = "admin@demo.local"
ADMIN_PASSWORD = "adminpass123"
STAFF_EMAIL = "staff@demo.local"
STAFF_PASSWORD = "staffpass123"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables before seeding (destroys existing data).",
    )
    return parser.parse_args(argv)


def _seed(session_factory) -> None:
    with session_factory() as db:
        now = datetime.now(timezone.utc)

        admin = User(
            email=ADMIN_EMAIL,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role=UserRole.ADMIN,
        )
        staff = User(
            email=STAFF_EMAIL,
            hashed_password=hash_password(STAFF_PASSWORD),
            role=UserRole.STAFF,
        )
        db.add_all([admin, staff])
        db.flush()

        starters = Category(name="Starters", display_order=1)
        mains = Category(name="Mains", display_order=2)
        desserts = Category(name="Desserts", display_order=3)
        db.add_all([starters, mains, desserts])
        db.flush()

        # (category, name, description, prep_time, is_daily_special, amount_cents)
        items_spec = [
            (starters, "Caesar Salad", "Romaine, parmesan, croutons, anchovy dressing.", 8, False, 1100),
            (starters, "Tomato Soup", "Heirloom tomatoes, basil oil, sourdough toast.", 10, True, 950),
            (starters, "Bruschetta", "Grilled bread, marinated tomato, garlic, olive oil.", 7, False, 850),
            (mains, "Margherita Pizza", "San Marzano tomato, fresh mozzarella, basil.", 14, False, 1600),
            (mains, "Grilled Salmon", "Atlantic salmon, lemon butter, seasonal vegetables.", 18, False, 2400),
            (mains, "Mushroom Risotto", "Arborio rice, porcini, parmesan, truffle oil.", 20, True, 1800),
            (mains, "Cheeseburger", "Brioche bun, aged cheddar, bacon jam, fries.", 15, False, 1750),
            (desserts, "Tiramisu", "Espresso-soaked ladyfingers, mascarpone, cocoa.", 5, False, 900),
            (desserts, "Crème Brûlée", "Vanilla custard, caramelized sugar crust.", 5, False, 950),
        ]

        items: list[MenuItem] = []
        for cat, name, desc, prep, special, cents in items_spec:
            item = MenuItem(
                category_id=cat.id,
                name=name,
                description=desc,
                prep_time_minutes=prep,
                is_daily_special=special,
            )
            db.add(item)
            db.flush()
            price = Price(
                menu_item_id=item.id,
                amount_cents=cents,
                effective_from=now,
                created_by=admin.id,
            )
            db.add(price)
            db.flush()
            items.append(item)

        menu = Menu(
            name="Dinner Menu",
            version=1,
            published_at=now,
            created_by=admin.id,
        )
        db.add(menu)
        db.flush()

        for item in items:
            current_price = (
                db.query(Price)
                .filter(Price.menu_item_id == item.id, Price.effective_to.is_(None))
                .one()
            )
            db.add(
                MenuItemInMenu(
                    menu_id=menu.id,
                    menu_item_id=item.id,
                    price_id=current_price.id,
                )
            )

        db.commit()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    engine = get_engine()

    # Schema is owned by Alembic — seed.py must not drift from migrations.
    # If the tables aren't there, refuse rather than silently creating
    # whatever the current ORM metadata looks like.
    if args.reset:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    else:
        inspector = inspect(engine)
        if "users" not in inspector.get_table_names():
            print(
                "Schema not found: did you run `alembic upgrade head` first?\n"
                "  (Or pass --reset to drop+recreate tables from ORM metadata.)",
                file=sys.stderr,
            )
            return 1

    session_factory = get_session_factory()

    # Idempotency check — refuse to double-seed if the admin user already exists.
    if not args.reset:
        with session_factory() as db:
            existing_admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
            if existing_admin is not None:
                print(
                    f"Database already seeded (found {ADMIN_EMAIL}). "
                    "Run with --reset to wipe and reseed.",
                    file=sys.stderr,
                )
                return 0

    _seed(session_factory)

    print("\n=== Seed complete ===")
    print(f"  Admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"  Staff: {STAFF_EMAIL} / {STAFF_PASSWORD}")
    print("\nNext steps:")
    print("  1. uvicorn app.main:app --reload")
    print("  2. Open http://localhost:8000/docs")
    print("  3. Authorize with the admin credentials above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
