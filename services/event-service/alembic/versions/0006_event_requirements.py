"""SPM-80: structured venue, accessibility, and equipment requirements

Revision ID: 0006_event_requirements
Revises: 0005_change_request_details
Create Date: 2026-10-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_event_requirements"
down_revision = "0005_change_request_details"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # A failed run can leave earlier columns behind while alembic_version stays put.
    columns = _columns("events")
    if "preferred_location" not in columns:
        op.add_column("events", sa.Column("preferred_location", sa.String(255), nullable=False, server_default=""))
    if "required_facilities" not in columns:
        op.add_column("events", sa.Column("required_facilities", sa.JSON(), nullable=True))
    # MySQL refuses a default on TEXT. Add it nullable, fill existing rows, then require a value.
    if "accessibility_note" not in columns:
        op.add_column("events", sa.Column("accessibility_note", sa.Text(), nullable=True))
    op.execute("UPDATE events SET accessibility_note = '' WHERE accessibility_note IS NULL")
    op.alter_column("events", "accessibility_note", existing_type=sa.Text(), nullable=False)
    if "accessibility_selections" not in columns:
        op.add_column("events", sa.Column("accessibility_selections", sa.JSON(), nullable=True))
    if "equipment_lines" not in columns:
        op.add_column("events", sa.Column("equipment_lines", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "equipment_lines")
    op.drop_column("events", "accessibility_selections")
    op.drop_column("events", "accessibility_note")
    op.drop_column("events", "required_facilities")
    op.drop_column("events", "preferred_location")
