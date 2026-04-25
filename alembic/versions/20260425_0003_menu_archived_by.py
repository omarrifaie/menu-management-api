"""add archived_by to menus

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25

Adds a nullable archived_by column on menus, foreign-keyed to users.id
with ON DELETE RESTRICT (matching created_by). The column records which
admin archived each menu so the audit trail covers archival as well as
publication.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("menus") as batch_op:
        batch_op.add_column(sa.Column("archived_by", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_menus_archived_by",
            "users",
            ["archived_by"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("menus") as batch_op:
        batch_op.drop_constraint("fk_menus_archived_by", type_="foreignkey")
        batch_op.drop_column("archived_by")
