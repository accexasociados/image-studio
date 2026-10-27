"""biblioteca de fotos de fondo para las escenas

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backgrounds",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("floor_y", sa.Float(), nullable=False),
        sa.Column("center_x", sa.Float(), nullable=False),
        sa.Column("piece_height", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("backgrounds")
