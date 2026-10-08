"""SPM-120: emergency access and known restrictions for each venue, for safety review

Revision ID: a3f1c9e7d520
Revises: e7b2c4d91f03
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a3f1c9e7d520"
down_revision: Union[str, None] = "e7b2c4d91f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MySQL cannot default a TEXT column, so these start empty (NULL) and read as "".
    op.add_column("venues", sa.Column("emergency_access", sa.Text(), nullable=True))
    op.add_column("venues", sa.Column("restrictions", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("venues", "restrictions")
    op.drop_column("venues", "emergency_access")
