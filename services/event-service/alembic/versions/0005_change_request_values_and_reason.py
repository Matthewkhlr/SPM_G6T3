"""SPM-106: a change request keeps the values it would replace and the coordinator's reason

Revision ID: 0005_change_request_details
Revises: 0004_clarification_threads
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_change_request_details"
down_revision = "0004_clarification_threads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event_change_requests", sa.Column("current_values", sa.JSON(), nullable=True))
    op.add_column("event_change_requests", sa.Column("decision_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("event_change_requests", "decision_reason")
    op.drop_column("event_change_requests", "current_values")
