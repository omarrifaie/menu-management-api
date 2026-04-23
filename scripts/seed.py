"""Populate the database with a demo dataset.

Run from the project root::

    python -m scripts.seed

The script is idempotent in the sense that it creates a fresh set of
tables if they don't exist — but it does not deduplicate data, so
running it twice against the same database will either double up or
fail on unique constraints. Use it on an empty database.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

# Allow running as `python scripts/seed.py` in addition to `python -m scripts.seed`.
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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


def main() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = get_session_factory()

    with Session() as db:
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

    print("\n=== Seed complete ===")
    print(f"  Admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"  Staff: {STAFF_EMAIL} / {STAFF_PASSWORD}")
    print("\nNext steps:")
    print("  1. uvicorn app.main:app --reload")
    print("  2. Open http://localhost:8000/docs")
    print("  3. Authorize with the admin credentials above.")


if __name__ == "__main__":
    main()
