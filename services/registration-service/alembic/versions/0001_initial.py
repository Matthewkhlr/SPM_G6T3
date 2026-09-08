"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registration_windows",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("opens_at", sa.DateTime(), nullable=False),
        sa.Column("closes_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "attendee_registrations",
        sa.Column("attendee_registration_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("registration_windows.event_id"), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("attendee_name", sa.String(255), nullable=False),
        sa.Column("attendee_email", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("attendee_registrations")
    op.drop_table("registration_windows")
