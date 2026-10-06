"""venue setup minutes (SPM-110)

Revision ID: d4e8a1c09b21
Revises: c1d5e8a2f7b3
Create Date: 2026-10-06 14:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e8a1c09b21"
down_revision: Union[str, None] = "c1d5e8a2f7b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "venues",
        sa.Column("setup_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE venues SET setup_minutes = CASE venue_id "
        "WHEN 'v1' THEN 30 WHEN 'v2' THEN 15 WHEN 'v3' THEN 45 WHEN 'v4' THEN 10 "
        "ELSE setup_minutes END"
    )
    op.alter_column("venues", "setup_minutes", server_default=None)


def downgrade() -> None:
    op.drop_column("venues", "setup_minutes")
