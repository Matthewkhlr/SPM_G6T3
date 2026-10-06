"""SPM-77: shortfall, alternative, and reserved quantity on an equipment request

Revision ID: e8c1a2b34d50
Revises: d3a9c6e1b4f2
Create Date: 2026-10-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "e8c1a2b34d50"
down_revision = "d3a9c6e1b4f2"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    columns = _columns("equipment_requests")
    # MySQL refuses a default on TEXT. Add it nullable, fill existing rows, then require a value.
    if "decision_reason" not in columns:
        op.add_column("equipment_requests", sa.Column("decision_reason", sa.Text(), nullable=True))
    op.execute("UPDATE equipment_requests SET decision_reason = '' WHERE decision_reason IS NULL")
    op.alter_column("equipment_requests", "decision_reason", existing_type=sa.Text(), nullable=False)
    if "alternative_equipment_id" not in columns:
        op.add_column("equipment_requests", sa.Column("alternative_equipment_id", sa.String(64), nullable=True))
    if "shortfall" not in columns:
        op.add_column("equipment_requests", sa.Column("shortfall", sa.Integer(), nullable=False, server_default="0"))
    if "reserved_quantity" not in columns:
        op.add_column(
            "equipment_requests", sa.Column("reserved_quantity", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    op.drop_column("equipment_requests", "reserved_quantity")
    op.drop_column("equipment_requests", "shortfall")
    op.drop_column("equipment_requests", "alternative_equipment_id")
    op.drop_column("equipment_requests", "decision_reason")
