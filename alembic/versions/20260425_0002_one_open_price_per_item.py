"""enforce single open price per menu item via partial unique index

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25

Adds a partial unique index on prices(menu_item_id) WHERE effective_to IS
NULL so the database itself rejects two open price rows for the same item.
This closes a small race window in POST /menu-items/{id}/prices where two
concurrent transactions could each read no open row, both insert, and
leave duplicate "current" rows. Both Postgres and SQLite support partial
indexes with the same syntax.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_prices_one_open_per_item",
        "prices",
        ["menu_item_id"],
        unique=True,
        postgresql_where=sa.text("effective_to IS NULL"),
        sqlite_where=sa.text("effective_to IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_prices_one_open_per_item", table_name="prices")
