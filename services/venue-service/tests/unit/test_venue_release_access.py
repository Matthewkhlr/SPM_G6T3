"""Only the people who can cancel an event may release its venue bookings, and
Venue Staff are not emailed about a cancellation they made themselves."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.clients import notify_venue_staff
from app.schemas.venue import EventFacts, OperatingHours
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, VenueCase, booking_create, venue_create
from tests.unit.test_venue_route_guards import HEADERS

ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EVENT = EventFacts(
    eventName="AI Summit",
    status="cancelled",
    coordinatorId="u-coord",
    organisationId="org-1",
    expectedAttendance=10,
    proposedStartAt=datetime(2030, 1, 7, 10),
    proposedEndAt=datetime(2030, 1, 7, 12),
)


def user(role, user_id, organisation_id=None):
    return {"userId": user_id, "userName": user_id, "role": role, "organisationId": organisation_id}


class TestWhoMayRelease(VenueCase):
    def allowed(self, caller):
        try:
            self.service.check_release_allowed(caller, EVENT)
            return True
        except HTTPException as exc:
            self.assertEqual(exc.status_code, 403)
            self.assertEqual(
                exc.detail, "Only the coordinator assigned to this event, or its organiser, can release its venue bookings."
            )
            return False

    def test_the_assigned_coordinator_and_the_events_own_organisers_may_release(self):
        self.assertTrue(self.allowed(user("coordinator", "u-coord")))
        self.assertTrue(self.allowed(user("organiser", "u-org", "org-1")))
        self.assertTrue(self.allowed(user("organiser", "u-colleague", "org-1")))

    def test_anyone_else_is_refused(self):
        for caller in (
            user("coordinator", "u-other-coord"),
            user("organiser", "u-other-client", "org-2"),
            user("organiser", "u-no-org"),
            user("venue", "u-coord"),
            user("techsupport", "u-tech", "org-1"),
        ):
            with self.subTest(caller=caller):
                self.assertFalse(self.allowed(caller))

    def test_an_event_without_a_coordinator_or_client_lets_nobody_in_by_those_routes(self):
        bare = EVENT.model_copy(update={"coordinatorId": None, "organisationId": None})
        for caller in (user("coordinator", "u-coord"), user("organiser", "u-org")):
            with self.subTest(caller=caller), self.assertRaises(HTTPException):
                self.service.check_release_allowed(caller, bare)


class TestReleaseRoute(VenueCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        self.venue_id = self.service.create_venue(
            venue_create(operatingHours=[OperatingHours(day=d, opens="00:00", closes="24:00") for d in ALL_DAYS]),
            CALLER,
        ).venueId
        self.event = patch("app.routers.venue.fetch_event_facts", return_value=EVENT)
        self.fetch = self.event.start()

    def tearDown(self):
        self.event.stop()
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def release(self, caller):
        with patch("app.routers.venue.resolve_caller", return_value=caller):
            return self.client.post("/venues/bookings/release", headers=HEADERS, json={"eventId": "e1"})

    def test_another_events_coordinator_or_another_client_cannot_free_its_rooms(self):
        for caller in (user("coordinator", "u-other-coord"), user("organiser", "u-other-client", "org-2")):
            with self.subTest(caller=caller):
                self.assertEqual(self.release(caller).status_code, 403)
        self.fetch.assert_called_with("e1", HEADERS["Authorization"])

    def test_the_events_own_organiser_can_release(self):
        released = self.release(user("organiser", "u-org", "org-1"))

        self.assertEqual(released.status_code, 200)
        self.assertEqual(released.json(), [])


class TestNotifyingVenueStaff(VenueCase):
    USERS = [
        {"userId": "u-vinod", "email": "vinod@x.com", "role": "venue"},
        {"userId": "u-vera", "email": "vera@x.com", "role": "venue"},
    ]

    def reply(self, status_code, body=None):
        response = MagicMock(status_code=status_code)
        response.json.return_value = body
        return response

    def test_the_venue_staff_member_who_cancelled_is_not_emailed_about_it(self):
        with patch("app.orchestration.clients.httpx.get", return_value=self.reply(200, self.USERS)), patch(
            "app.orchestration.clients.httpx.post", return_value=self.reply(200)
        ) as post:
            sent = notify_venue_staff("Subject", "Body", "Bearer t", skip_user_id="u-vinod")

        self.assertEqual(sent, 1)
        self.assertEqual([c.kwargs["json"]["to"] for c in post.call_args_list], ["vera@x.com"])

    def test_cancelling_skips_whoever_did_it(self):
        venue_id = self.service.create_venue(venue_create(), CALLER).venueId
        booking = self.service.create_booking(booking_create(venue_id, eventId="e1"), "u-coord")
        self.service.approve_booking(booking.bookingId, "u-venue", None)
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        try:
            with patch("app.routers.venue.resolve_caller", return_value=user("venue", "u-vinod")), patch(
                "app.routers.venue.fetch_event_facts", return_value=EVENT
            ), patch("app.routers.venue.notify_venue_staff") as notify, TestClient(app) as client:
                cancelled = client.post(f"/venues/bookings/{booking.bookingId}/cancel", headers=HEADERS)
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(notify.call_args.kwargs, {"skip_user_id": "u-vinod"})
