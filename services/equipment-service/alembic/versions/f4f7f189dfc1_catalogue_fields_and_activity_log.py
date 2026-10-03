"""catalogue fields and activity log

Revision ID: f4f7f189dfc1
Revises: 0001_initial
Create Date: 2026-09-24 12:47:22.662292

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = 'f4f7f189dfc1'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # A failed run can leave these objects behind while alembic_version stays at 0001.
    # Skip anything already present so a retry and a fresh database both finish.
    if not inspect(op.get_bind()).has_table("equipment_activity_log"):
        op.create_table(
        "equipment_activity_log",
        sa.Column("log_id", sa.String(length=64), nullable=False),
        sa.Column("equipment_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("changed_by", sa.String(length=64), nullable=False),
        sa.Column("changed_by_name", sa.String(length=255), nullable=False),
        sa.Column("changed_by_role", sa.String(length=64), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment_info.equipment_id"]),
        sa.PrimaryKeyConstraint("log_id"),
        )
    columns = _columns("equipment_info")
    # server_default fills rows that already exist; the backfill below replaces
    # the placeholders. Fresh seed inserts set code and home_location themselves.
    if "code" not in columns:
        op.add_column(
            "equipment_info",
            sa.Column("code", sa.String(length=64), nullable=False, server_default=""),
        )
    if "home_location" not in columns:
        op.add_column(
            "equipment_info",
            sa.Column("home_location", sa.String(length=255), nullable=False, server_default=""),
        )
    # MySQL refuses a default on TEXT. Add it nullable, fill existing rows, then require a value.
    if "technical_notes" not in columns:
        op.add_column("equipment_info", sa.Column("technical_notes", sa.Text(), nullable=True))
    if "damaged_count" not in columns:
        op.add_column(
            "equipment_info",
            sa.Column("damaged_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if "maintenance_count" not in columns:
        op.add_column(
            "equipment_info",
            sa.Column("maintenance_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if "retired_count" not in columns:
        op.add_column(
            "equipment_info",
            sa.Column("retired_count", sa.Integer(), nullable=False, server_default="0"),
        )
    op.execute(
        """
        UPDATE equipment_info
        SET code = equipment_id
        WHERE code = ''
        """
    )
    op.execute(
        """
        UPDATE equipment_info
        SET home_location = location
        WHERE home_location = ''
        """
    )
    op.execute("UPDATE equipment_info SET technical_notes = '' WHERE technical_notes IS NULL")
    op.alter_column("equipment_info", "technical_notes", existing_type=sa.Text(), nullable=False)
    op.create_unique_constraint("uq_equipment_info_code", "equipment_info", ["code"])


def downgrade() -> None:
    op.drop_constraint("uq_equipment_info_code", "equipment_info", type_="unique")
    op.drop_column("equipment_info", "retired_count")
    op.drop_column("equipment_info", "maintenance_count")
    op.drop_column("equipment_info", "damaged_count")
    op.drop_column("equipment_info", "technical_notes")
    op.drop_column("equipment_info", "home_location")
    op.drop_column("equipment_info", "code")
    op.drop_table("equipment_activity_log")
