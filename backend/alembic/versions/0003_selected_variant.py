"""variante elegida al aprobar y máscara corregida a mano

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("images") as batch:
        batch.add_column(sa.Column("selected_variant", sa.String(length=10), nullable=True))
        batch.add_column(sa.Column("mask_edited", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("images") as batch:
        batch.drop_column("mask_edited")
        batch.drop_column("selected_variant")
