"""venue booking re-verification flag (SPM-71 AC4)

Revision ID: c1d5e8a2f7b3
Revises: 67ee92bd65e7
Create Date: 2026-10-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1d5e8a2f7b3'
down_revision: Union[str, None] = '67ee92bd65e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'venue_bookings',
        sa.Column('needs_reverification', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('venue_bookings', sa.Column('reverification_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('venue_bookings', 'reverification_note')
    op.drop_column('venue_bookings', 'needs_reverification')
