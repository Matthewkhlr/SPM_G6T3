from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, END, START, VenueCase, booking_create, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as


class ReverificationCase(VenueCase):
    def setUp(self):
        super().setUp()
        self.venue_id = self.service.create_venue(venue_create(), CALLER).venueId

    def booking(self, event_id="e1", approve=True, days_later=0):
        # Different events need different days: two overlapping confirmed bookings
        # can no longer exist (SPM-64).
        shift = timedelta(days=days_later)
        created = self.service.create_booking(
            booking_create(self.venue_id, eventId=event_id, startsAt=START + shift, endsAt=END + shift), "u-coord"
        )
        if approve:
            self.service.approve_booking(created.bookingId, "u-venue", "Free")
        return created.bookingId


class TestBookingReverification(ReverificationCase):
    def test_only_the_events_approved_bookings_are_flagged_and_stay_approved(self):
        approved = self.booking()
        pending = self.booking(approve=False)
        other_event = self.booking(event_id="e2", days_later=1)

        flagged = self.service.flag_for_reverification("e1", "Expected attendance: 20 -> 200")

        self.assertEqual([row.bookingId for row in flagged], [approved])
        self.assertTrue(flagged[0].needsReverification)
        self.assertEqual(flagged[0].status, "approved")
        self.assertEqual(flagged[0].reverificationNote, "Expected attendance: 20 -> 200")
        self.assertEqual(flagged[0].venueName, "Marina Hall A")
        self.assertTrue(self.service.get_booking(approved).needsReverification)
        self.assertFalse(self.service.get_booking(pending).needsReverification)
        self.assertFalse(self.service.get_booking(other_event).needsReverification)

    def test_a_flagged_booking_still_holds_the_venue(self):
        approved = self.booking()
        self.service.flag_for_reverification("e1", "Start moved")

        venue = self.service.get_venue(self.venue_id)
        held = self.service.commitments(venue, START, END, exclude_event_id="another-event")

        self.assertEqual([row.bookingId for row in held.confirmed], [approved])

    def test_an_event_without_a_confirmed_booking_flags_nothing(self):
        self.booking(approve=False)

        self.assertEqual(self.service.flag_for_reverification("e1", "Start moved"), [])

    def test_a_new_booking_is_not_flagged(self):
        created = self.service.get_booking(self.booking(approve=False))

        self.assertFalse(created.needsReverification)
        self.assertIsNone(created.reverificationNote)


class TestBookingReverificationRoute(ReverificationCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_a_coordinator_can_flag_an_events_bookings(self):
        approved = self.booking()

        with signed_in_as("coordinator"):
            flagged = self.client.post(
                "/venues/bookings/reverification", headers=HEADERS, json={"eventId": "e1", "reason": "Start moved"}
            )

        self.assertEqual(flagged.status_code, 200)
        self.assertEqual([row["bookingId"] for row in flagged.json()], [approved])
        self.assertTrue(flagged.json()[0]["needsReverification"])

    def test_other_roles_cannot_flag_bookings(self):
        self.booking()
        for role in ("venue", "organiser", "techsupport", "attendee"):
            with signed_in_as(role):
                denied = self.client.post("/venues/bookings/reverification", headers=HEADERS, json={"eventId": "e1"})
            self.assertEqual(denied.status_code, 403, role)
        self.assertFalse(self.service.list_bookings(event_id="e1")[0].needsReverification)
