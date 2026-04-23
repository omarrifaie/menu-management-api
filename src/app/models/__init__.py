"""SQLAlchemy ORM models.

Importing this package registers every table on ``Base.metadata``, which is
what Alembic's autogenerate and :meth:`Base.metadata.create_all` rely on.
"""

from app.models.base import Base
from app.models.category import Category
from app.models.menu import Menu, MenuItemInMenu
from app.models.menu_item import MenuItem
from app.models.price import Price
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "Category",
    "Menu",
    "MenuItem",
    "MenuItemInMenu",
    "Price",
    "User",
    "UserRole",
]
