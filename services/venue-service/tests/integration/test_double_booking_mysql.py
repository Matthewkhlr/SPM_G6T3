"""SPM-64 against the real MySQL: the database itself refuses two confirmed
bookings whose occupied windows overlap (AC3, AC6), and two approvals for
clashing requests at the same moment leave exactly one confirmed (AC7)."""

import os
import threading
import unittest
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.dao.venue_activity_log_dao import VenueActivityLogDAO
from app.dao.venue_booking_dao import VenueBookingDAO
from app.dao.venue_dao import VenueDAO
from app.dao.venue_unavailability_dao import VenueUnavailabilityDAO
from app.services.venue_service import VenueService

URL = os.environ.get("VENUE_MYSQL_URL", "mysql+pymysql://connectsphere:connectsphere@127.0.0.1:3307/venue")
# Far in the future, so these rows never meet real bookings.
DAY = datetime(2099, 3, 2)


def at(hour, minute=0):
    return DAY + timedelta(hours=hour, minutes=minute)


def _reachable() -> str | None:
    try:
        with create_engine(URL).connect() as conn:
            found = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = DATABASE() "
                    "AND TRIGGER_NAME LIKE 'venue_bookings_no_overlap_%'"
                )
            ).scalar()
    except OperationalError as exc:
        return f"MySQL not reachable: {exc.orig}"
    return None if found == 2 else "the SPM-64 triggers are missing; run scripts/migrate.py"


SKIP = _reachable()


@unittest.skipIf(SKIP, SKIP or "")
class MySQLCase(unittest.TestCase):
    """A throwaway venue with 30 minutes setup and 60 minutes turnaround, so a
    10:00 to 12:00 booking occupies it from 09:30 to 13:00."""

    def setUp(self):
        self.engine = create_engine(URL, pool_size=4)
        self.Session = sessionmaker(bind=self.engine, autoflush=False)
        self.venue_id = f"it-{uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO venues (venue_id, code, name, location, address, floor, description, facilities, "
                    "accessibility, layouts, operating_hours, setup_minutes, turnaround_minutes, is_active, created_at) "
                    "VALUES (:id, 'IT', 'Integration Hall', 'Test', '', '', '', '[]', '[]', "
                    "'[{\"name\": \"Theatre\", \"capacity\": 100}]', '[]', 30, 60, 1, :now)"
                ),
                {"id": self.venue_id, "now": datetime.utcnow()},
            )

    def tearDown(self):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM venue_bookings WHERE venue_id = :id"), {"id": self.venue_id})
            conn.execute(text("DELETE FROM venues WHERE venue_id = :id"), {"id": self.venue_id})
        self.engine.dispose()

    def insert(self, starts_at, ends_at, status="approved"):
        booking_id = str(uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO venue_bookings (booking_id, venue_id, event_id, requested_by, status, starts_at, "
                    "ends_at, setup_starts_at, teardown_ends_at, requirements_snapshot, needs_reverification, "
                    "created_at) VALUES (:id, :venue, :event, 'u-it', :status, :starts, :ends, :starts, :ends, '', 0, :now)"
                ),
                {
                    "id": booking_id,
                    "venue": self.venue_id,
                    "event": f"e-{booking_id[:6]}",
                    "status": status,
                    "starts": starts_at,
                    "ends": ends_at,
                    "now": datetime.utcnow(),
                },
            )
        return booking_id

    def assert_refused_by_the_database(self, action):
        with self.assertRaises(OperationalError) as ctx:
            action()
        self.assertEqual(ctx.exception.orig.args[0], 1644)
        self.assertIn("already has a confirmed booking at an overlapping time", ctx.exception.orig.args[1])

    def statuses(self):
        with self.engine.connect() as conn:
            return sorted(
                conn.execute(
                    text("SELECT status FROM venue_bookings WHERE venue_id = :id"), {"id": self.venue_id}
                ).scalars()
            )


class TestTheDatabaseRefusesOverlaps(MySQLCase):
    """AC3: enforced in the database, not only in application code."""

    def test_a_second_overlapping_confirmed_booking_cannot_be_written(self):
        self.insert(at(10), at(12))

        self.assert_refused_by_the_database(lambda: self.insert(at(11), at(13)))
        self.assertEqual(self.statuses(), ["approved"])

    def test_a_pending_request_cannot_be_turned_into_an_overlapping_confirmed_booking(self):
        self.insert(at(10), at(12))
        pending = self.insert(at(12), at(13), status="pending")

        def approve_directly():
            with self.engine.begin() as conn:
                conn.execute(
                    text("UPDATE venue_bookings SET status = 'approved' WHERE booking_id = :id"), {"id": pending}
                )

        # Event times only touch, but setup and turnaround make the windows overlap (AC6).
        self.assert_refused_by_the_database(approve_directly)
        self.assertEqual(self.statuses(), ["approved", "pending"])

    def test_occupied_windows_that_only_touch_are_allowed(self):
        self.insert(at(10), at(12))

        self.insert(at(13, 30), at(14))
        self.insert(at(7), at(8, 30))

        self.assertEqual(self.statuses(), ["approved", "approved", "approved"])

    def test_pending_requests_and_other_changes_to_a_confirmed_booking_are_not_blocked(self):
        held = self.insert(at(10), at(12))
        self.insert(at(10), at(12), status="pending")

        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE venue_bookings SET needs_reverification = 1 WHERE booking_id = :id"), {"id": held}
            )

        self.assertEqual(self.statuses(), ["approved", "pending"])


class TestSimultaneousApprovals(MySQLCase):
    """AC7: exactly one of two clashing approvals made at the same moment succeeds."""

    def race(self, attempt):
        first = self.insert(at(10), at(12), status="pending")
        second = self.insert(at(11), at(13), status="pending")
        start = threading.Barrier(2)
        outcomes = {}

        def run(booking_id):
            start.wait()
            outcomes[booking_id] = attempt(booking_id)

        threads = [threading.Thread(target=run, args=(booking_id,)) for booking_id in (first, second)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        return sorted(outcomes.values())

    def test_two_approvals_through_the_service_leave_one_confirmed_and_explain_the_other(self):
        def approve(booking_id):
            session = self.Session()
            service = VenueService(
                session,
                VenueDAO(session),
                VenueActivityLogDAO(session),
                VenueBookingDAO(session),
                VenueUnavailabilityDAO(session),
            )
            try:
                service.approve_booking(booking_id, "u-venue", "race")
                return "approved"
            except HTTPException as exc:
                return f"{exc.status_code}: {'already confirmed' if 'already confirmed' in exc.detail else exc.detail}"
            finally:
                session.close()

        self.assertEqual(self.race(approve), ["409: already confirmed", "approved"])
        self.assertEqual(self.statuses(), ["approved", "pending"])

    def test_two_direct_writes_at_once_leave_one_confirmed(self):
        def write(booking_id):
            try:
                with self.engine.begin() as conn:
                    conn.execute(
                        text("UPDATE venue_bookings SET status = 'approved' WHERE booking_id = :id"), {"id": booking_id}
                    )
                return "approved"
            except OperationalError as exc:
                return f"refused {exc.orig.args[0]}"

        self.assertEqual(self.race(write), ["approved", "refused 1644"])
        self.assertEqual(self.statuses(), ["approved", "pending"])
