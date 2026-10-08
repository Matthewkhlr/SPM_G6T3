"""SPM-72: who confirmed an event and when; safety approval no longer reads as preparation

Revision ID: 0009_event_confirmation
Revises: 0008_safety_reviews
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_event_confirmation"
down_revision = "0008_safety_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("confirmed_by", sa.String(64), nullable=True))
    op.add_column("events", sa.Column("confirmed_at", sa.DateTime(), nullable=True))
    # SPM-120: only a safety approval ever set "preparing". Preparation now starts
    # once the coordinator confirms, so those events wait in "safety approved".
    op.execute("UPDATE events SET status = 'safety approved' WHERE status = 'preparing'")


def downgrade() -> None:
    op.execute("UPDATE events SET status = 'preparing' WHERE status = 'safety approved'")
    op.drop_column("events", "confirmed_at")
    op.drop_column("events", "confirmed_by")
