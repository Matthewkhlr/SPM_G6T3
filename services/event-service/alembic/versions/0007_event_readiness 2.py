"""SPM-5: coordinator readiness follow-up lines

Revision ID: 0007_event_readiness
Revises: 0006_event_requirements
Create Date: 2026-10-06
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_event_readiness"
down_revision = "0006_event_requirements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_readiness_items",
        sa.Column("item_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False, index=True),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("handler_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("handler_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("handler_email", sa.String(255), nullable=False, server_default=""),
        sa.Column("handler_phone", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="outstanding"),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("event_readiness_items")
