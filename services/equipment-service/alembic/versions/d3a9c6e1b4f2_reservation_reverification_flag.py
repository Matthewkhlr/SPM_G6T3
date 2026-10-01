"""equipment reservation re-verification flag (SPM-71 AC4)

Revision ID: d3a9c6e1b4f2
Revises: b7e2a4c91d10
Create Date: 2026-10-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3a9c6e1b4f2"
down_revision: Union[str, None] = "b7e2a4c91d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "equipment_reservations",
        sa.Column("needs_reverification", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("equipment_reservations", sa.Column("reverification_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("equipment_reservations", "reverification_note")
    op.drop_column("equipment_reservations", "needs_reverification")
