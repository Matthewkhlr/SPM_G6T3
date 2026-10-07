"""SPM-64 AC3: the database refuses two confirmed bookings with overlapping occupied windows.

A booking's occupied window is its event start minus the venue's setup time
through its event end plus the venue's turnaround time (AC2). Two bookings on
the same venue share those minutes, so their windows overlap exactly when one
event starts before the other ends plus setup plus turnaround. Windows that
only touch do not overlap (AC6).

The triggers lock the venue's row first, so two approvals for the same venue
are checked one after the other and cannot both pass (AC7).

Revision ID: e7b2c4d91f03
Revises: d4e8a1c09b21
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e7b2c4d91f03"
down_revision: Union[str, None] = "d4e8a1c09b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MESSAGE = "This venue already has a confirmed booking at an overlapping time, including setup and turnaround."


def _check(trigger: str, event: str, condition: str) -> str:
    return f"""
CREATE TRIGGER {trigger} BEFORE {event} ON venue_bookings
FOR EACH ROW
BEGIN
    DECLARE reach INT;
    DECLARE clashes INT;
    IF {condition} THEN
        SELECT setup_minutes + turnaround_minutes INTO reach
        FROM venues WHERE venue_id = NEW.venue_id FOR UPDATE;
        SELECT COUNT(*) INTO clashes
        FROM venue_bookings other
        WHERE other.venue_id = NEW.venue_id
          AND other.status = 'approved'
          AND other.booking_id <> NEW.booking_id
          AND other.starts_at < NEW.ends_at + INTERVAL reach MINUTE
          AND other.ends_at > NEW.starts_at - INTERVAL reach MINUTE
        FOR SHARE;
        IF clashes > 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '{MESSAGE}';
        END IF;
    END IF;
END
"""


def upgrade() -> None:
    if op.get_bind().dialect.name != "mysql":
        return
    op.execute(_check("venue_bookings_no_overlap_insert", "INSERT", "NEW.status = 'approved'"))
    op.execute(
        _check(
            "venue_bookings_no_overlap_update",
            "UPDATE",
            "NEW.status = 'approved' AND (OLD.status <> 'approved' OR NEW.venue_id <> OLD.venue_id"
            " OR NEW.starts_at <> OLD.starts_at OR NEW.ends_at <> OLD.ends_at)",
        )
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "mysql":
        return
    op.execute("DROP TRIGGER IF EXISTS venue_bookings_no_overlap_update")
    op.execute("DROP TRIGGER IF EXISTS venue_bookings_no_overlap_insert")
