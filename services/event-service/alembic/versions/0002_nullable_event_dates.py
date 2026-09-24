"""make proposed_start_at / proposed_end_at nullable for drafts

Revision ID: 0002_nullable_event_dates
Revises: 0001_initial
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_nullable_event_dates"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("events", "proposed_start_at", existing_type=sa.DateTime(), nullable=True)
    op.alter_column("events", "proposed_end_at", existing_type=sa.DateTime(), nullable=True)


def downgrade() -> None:
    op.alter_column("events", "proposed_end_at", existing_type=sa.DateTime(), nullable=False)
    op.alter_column("events", "proposed_start_at", existing_type=sa.DateTime(), nullable=False)
