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
        "events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("organiser_id", sa.String(64), nullable=False),
        sa.Column("organisation_id", sa.String(64), nullable=True),
        sa.Column("coordinator_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("proposed_start_at", sa.DateTime(), nullable=False),
        sa.Column("proposed_end_at", sa.DateTime(), nullable=False),
        sa.Column("expected_attendance", sa.Integer(), nullable=False),
        sa.Column("venue_requirements", sa.Text(), nullable=False),
        sa.Column("accessibility_needs", sa.Text(), nullable=False),
        sa.Column("equipment_requirements", sa.Text(), nullable=False),
        sa.Column("layout_preference", sa.String(64), nullable=True),
        sa.Column("registration_enabled", sa.Boolean(), nullable=False),
        sa.Column("registration_opens_at", sa.DateTime(), nullable=True),
        sa.Column("registration_closes_at", sa.DateTime(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "event_reviews",
        sa.Column("review_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column("reviewer_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "event_assignments",
        sa.Column("assignment_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column("coordinator_id", sa.String(64), nullable=False),
        sa.Column("assigned_by", sa.String(64), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "event_change_requests",
        sa.Column("change_request_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("proposed_changes", sa.JSON(), nullable=True),
        sa.Column("affects_venue", sa.Boolean(), nullable=False),
        sa.Column("affects_equipment", sa.Boolean(), nullable=False),
        sa.Column("affects_registration", sa.Boolean(), nullable=False),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "event_status_history",
        sa.Column("history_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("changed_by", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("event_status_history")
    op.drop_table("event_change_requests")
    op.drop_table("event_assignments")
    op.drop_table("event_reviews")
    op.drop_table("events")
