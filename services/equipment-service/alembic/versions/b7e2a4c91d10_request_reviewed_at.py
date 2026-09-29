"""request reviewed at

Revision ID: b7e2a4c91d10
Revises: f4f7f189dfc1
Create Date: 2026-09-29 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "b7e2a4c91d10"
down_revision: Union[str, None] = "f4f7f189dfc1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("equipment_requests")}
    if "reviewed_at" not in columns:
        op.add_column("equipment_requests", sa.Column("reviewed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("equipment_requests", "reviewed_at")
