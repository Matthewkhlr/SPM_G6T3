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
        "equipment_info",
        sa.Column("equipment_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
    )
    op.create_table(
        "equipment_units",
        sa.Column("unit_id", sa.String(64), primary_key=True),
        sa.Column("equipment_id", sa.String(64), sa.ForeignKey("equipment_info.equipment_id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
    )
    op.create_table(
        "equipment_requests",
        sa.Column("request_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("equipment_id", sa.String(64), sa.ForeignKey("equipment_info.equipment_id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("technical_requirements", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "equipment_reservations",
        sa.Column("reservation_id", sa.String(64), primary_key=True),
        sa.Column("request_id", sa.String(64), sa.ForeignKey("equipment_requests.request_id"), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("equipment_id", sa.String(64), sa.ForeignKey("equipment_info.equipment_id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("equipment_reservations")
    op.drop_table("equipment_requests")
    op.drop_table("equipment_units")
    op.drop_table("equipment_info")
