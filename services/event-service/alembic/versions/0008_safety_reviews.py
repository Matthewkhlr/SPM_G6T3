"""SPM-120: safety reviews, one row per submission

Revision ID: 0008_safety_reviews
Revises: 0007_event_readiness
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_safety_reviews"
down_revision = "0007_event_readiness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_safety_reviews",
        sa.Column("review_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("events.event_id"), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("submitted_by", sa.String(64), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("crowd_movement", sa.Text(), nullable=False),
        sa.Column("equipment_placement", sa.Text(), nullable=False),
        sa.Column("package", sa.JSON(), nullable=False),
        sa.Column("decided_by", sa.String(64), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("affected", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("event_safety_reviews")
