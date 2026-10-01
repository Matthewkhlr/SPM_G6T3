"""SPM-71: internal notes, organiser contact, and a per-field edit log

Revision ID: 0003_event_edit_fields
Revises: 0002_nullable_event_dates
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_event_edit_fields"
down_revision = "0002_nullable_event_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("internal_notes", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("organiser_contact", sa.String(255), nullable=True))
    op.create_table(
        "event_field_changes",
        sa.Column("change_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("event_field_changes")
    op.drop_column("events", "organiser_contact")
    op.drop_column("events", "internal_notes")
