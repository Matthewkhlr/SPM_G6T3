"""SPM-120, change 6: Venue Staff and technical support send their arrangements to the Safety Officer

Revision ID: 0010_safety_handoff
Revises: 0009_event_confirmation
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_safety_handoff"
down_revision = "0009_event_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_safety_handoffs",
        sa.Column("event_id", sa.String(64), sa.ForeignKey("events.event_id"), primary_key=True),
        sa.Column("crowd_movement", sa.Text(), nullable=True),
        sa.Column("venue_sent_by", sa.String(64), nullable=True),
        sa.Column("venue_sent_at", sa.DateTime(), nullable=True),
        sa.Column("equipment_placement", sa.Text(), nullable=True),
        sa.Column("technical_sent_by", sa.String(64), nullable=True),
        sa.Column("technical_sent_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("event_safety_handoffs")
