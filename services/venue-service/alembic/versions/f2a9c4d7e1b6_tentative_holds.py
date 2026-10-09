"""SPM-116: a tentative hold on a pending venue booking request, with an expiry.

A hold reserves the venue for the request's occupied window until
`hold_expires_at`, unless it ends first. `hold_ended_at` and `hold_end_reason`
record how it ended (released by Venue Staff, or the request was approved,
rejected, withdrawn or cancelled). A hold whose expiry has passed simply stops
counting; no job is needed to clear it.

Revision ID: f2a9c4d7e1b6
Revises: a3f1c9e7d520
Create Date: 2026-10-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f2a9c4d7e1b6"
down_revision: Union[str, None] = "a3f1c9e7d520"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("venue_bookings", sa.Column("hold_expires_at", sa.DateTime(), nullable=True))
    op.add_column("venue_bookings", sa.Column("hold_placed_by", sa.String(length=64), nullable=True))
    op.add_column("venue_bookings", sa.Column("hold_placed_at", sa.DateTime(), nullable=True))
    op.add_column("venue_bookings", sa.Column("hold_ended_at", sa.DateTime(), nullable=True))
    op.add_column("venue_bookings", sa.Column("hold_end_reason", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("venue_bookings", "hold_end_reason")
    op.drop_column("venue_bookings", "hold_ended_at")
    op.drop_column("venue_bookings", "hold_placed_at")
    op.drop_column("venue_bookings", "hold_placed_by")
    op.drop_column("venue_bookings", "hold_expires_at")
