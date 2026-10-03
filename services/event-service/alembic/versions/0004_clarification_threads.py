"""SPM-68: clarification state on event_reviews, and the replies that thread under them

Revision ID: 0004_clarification_threads
Revises: 0003_event_edit_fields
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_clarification_threads"
down_revision = "0003_event_edit_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event_reviews", sa.Column("field", sa.String(64), nullable=True))
    op.add_column("event_reviews", sa.Column("status", sa.String(16), nullable=True))
    op.add_column("event_reviews", sa.Column("resolved_by", sa.String(64), nullable=True))
    op.add_column("event_reviews", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    # Clarifications raised before this revision had no state; none was ever resolved.
    op.execute("UPDATE event_reviews SET status = 'open' WHERE action = 'request_clarification'")
    op.create_table(
        "event_clarification_replies",
        sa.Column("reply_id", sa.String(64), primary_key=True),
        sa.Column("review_id", sa.String(64), sa.ForeignKey("event_reviews.review_id"), nullable=False),
        sa.Column("author_id", sa.String(64), nullable=False),
        sa.Column("author_role", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("event_clarification_replies")
    op.drop_column("event_reviews", "resolved_at")
    op.drop_column("event_reviews", "resolved_by")
    op.drop_column("event_reviews", "status")
    op.drop_column("event_reviews", "field")
