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
        "venues",
        sa.Column("venue_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("facilities", sa.JSON(), nullable=False),
        sa.Column("accessibility", sa.Text(), nullable=False),
        sa.Column("layouts", sa.JSON(), nullable=False),
        sa.Column("operating_hours", sa.String(255), nullable=False),
        sa.Column("turnaround_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "venue_unavailability",
        sa.Column("unavailability_id", sa.String(64), primary_key=True),
        sa.Column("venue_id", sa.String(64), sa.ForeignKey("venues.venue_id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "venue_bookings",
        sa.Column("booking_id", sa.String(64), primary_key=True),
        sa.Column("venue_id", sa.String(64), sa.ForeignKey("venues.venue_id"), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("setup_starts_at", sa.DateTime(), nullable=False),
        sa.Column("teardown_ends_at", sa.DateTime(), nullable=False),
        sa.Column("requirements_snapshot", sa.Text(), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_venue_bookings_venue_window",
        "venue_bookings",
        ["venue_id", "starts_at", "ends_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_venue_bookings_venue_window", table_name="venue_bookings")
    op.drop_table("venue_bookings")
    op.drop_table("venue_unavailability")
    op.drop_table("venues")
