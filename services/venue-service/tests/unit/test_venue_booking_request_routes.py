import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.clients import notify_venue_staff
from app.schemas.venue import EventFacts, OperatingHours
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, VenueCase, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EVENT = EventFacts(
    eventName="AI Summit",
    status="approved",
    coordinatorId="u-coordinator",  # the userId signed_in_as("coordinator") gives
    organisationId="org-1",
    organisationName="Apex Partners",
    expectedAttendance=10,
    layoutPreference="Theatre",
    proposedStartAt=datetime(2030, 1, 7, 10),
    proposedEndAt=datetime(2030, 1, 7, 12),
)


def response(status_code, body=None):
    reply = MagicMock(status_code=status_code)
    reply.json.return_value = body
    return reply


class TestBookingRequestRoutes(VenueCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        self.venue_id = self.service.create_venue(
            venue_create(operatingHours=[OperatingHours(day=d, opens="08:00", closes="18:00") for d in ALL_DAYS]),
            CALLER,
        ).venueId
        self.patches = {
            "event": patch("app.routers.venue.fetch_event_facts", return_value=EVENT),
            "notify": patch("app.routers.venue.notify_venue_staff", return_value=2),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}

    def tearDown(self):
        for p in self.patches.values():
            p.stop()
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def send(self, role="coordinator", **body):
        payload = {
            "venueId": self.venue_id,
            "eventId": "e1",
            "startsAt": "2030-01-07T10:00:00Z",
            "endsAt": "2030-01-07T12:00:00Z",
            "setupStartsAt": "2030-01-07T10:00:00Z",
            "teardownEndsAt": "2030-01-07T12:00:00Z",
            "coordinatorNotes": "Side door please.",
            **body,
        }
        with signed_in_as(role):
            return self.client.post("/venues/bookings", headers=HEADERS, json=payload)

    def call(self, role, method, path):
        with signed_in_as(role):
            return self.client.request(method, path, headers=HEADERS)

    def test_a_request_is_saved_with_the_event_facts_and_venue_staff_are_notified(self):
        sent = self.send()

        self.assertEqual(sent.status_code, 201)
        self.assertEqual(sent.json()["eventSnapshot"]["clientOrganisation"], "Apex Partners")
        self.mocks["event"].assert_called_once_with("e1", HEADERS["Authorization"])
        subject, body, authorization = self.mocks["notify"].call_args.args
        self.assertEqual(subject, "New venue request: AI Summit at Marina Hall A")
        self.assertIn("waiting in your pending queue", body)
        self.assertEqual(authorization, HEADERS["Authorization"])

    def test_a_refused_request_notifies_nobody(self):
        self.mocks["event"].return_value = EVENT.model_copy(update={"expectedAttendance": 500})

        refused = self.send()

        self.assertEqual(refused.status_code, 409)
        self.assertIn("not suitable", refused.json()["detail"])
        self.mocks["notify"].assert_not_called()

    def test_only_coordinators_can_send_or_withdraw_a_request(self):
        for role in ("venue", "techsupport", "organiser"):
            with self.subTest(role=role):
                self.assertEqual(self.send(role=role).status_code, 403)
                self.assertEqual(self.call(role, "POST", "/venues/bookings/x/withdraw").status_code, 403)

    def test_venue_staff_see_the_pending_queue_and_coordinators_see_their_events_requests(self):
        booking_id = self.send().json()["bookingId"]

        queue = self.call("venue", "GET", "/venues/bookings?status=pending")
        for_event = self.call("coordinator", "GET", "/venues/bookings?eventId=e1")
        one = self.call("venue", "GET", f"/venues/bookings/{booking_id}")

        self.assertEqual([row["bookingId"] for row in queue.json()], [booking_id])
        self.assertEqual([row["bookingId"] for row in for_event.json()], [booking_id])
        self.assertEqual(one.json()["coordinatorNotes"], "Side door please.")
        self.assertEqual(self.call("venue", "GET", "/venues/bookings/nope").status_code, 404)

    def test_other_roles_cannot_read_booking_requests(self):
        for role in ("techsupport", "organiser", "attendee"):
            with self.subTest(role=role):
                self.assertEqual(self.call(role, "GET", "/venues/bookings").status_code, 403)
                self.assertEqual(self.call(role, "GET", "/venues/bookings/x").status_code, 403)

    def test_withdrawing_tells_venue_staff(self):
        booking_id = self.send().json()["bookingId"]
        self.mocks["notify"].reset_mock()

        withdrawn = self.call("coordinator", "POST", f"/venues/bookings/{booking_id}/withdraw")

        self.assertEqual(withdrawn.status_code, 200)
        self.assertEqual(withdrawn.json()["status"], "withdrawn")
        self.assertEqual(
            self.mocks["notify"].call_args.args[0], "Venue request withdrawn: AI Summit at Marina Hall A"
        )
        self.mocks["event"].assert_called_with("e1", HEADERS["Authorization"])

    def test_after_reassignment_the_previous_coordinator_cannot_withdraw_and_nobody_is_notified(self):
        booking_id = self.send().json()["bookingId"]
        self.mocks["notify"].reset_mock()
        self.mocks["event"].return_value = EVENT.model_copy(update={"coordinatorId": "u-someone-else"})

        refused = self.call("coordinator", "POST", f"/venues/bookings/{booking_id}/withdraw")

        self.assertEqual(refused.status_code, 403)
        self.assertEqual(
            refused.json()["detail"], "Only the coordinator assigned to this event can withdraw its venue request."
        )
        self.mocks["notify"].assert_not_called()

    def test_withdrawing_an_unknown_request_is_not_found(self):
        self.assertEqual(self.call("coordinator", "POST", "/venues/bookings/nope/withdraw").status_code, 404)
        self.mocks["event"].assert_not_called()


class TestNotifyVenueStaff(unittest.TestCase):
    USERS = [
        {"email": "vinod@x.com", "role": "venue"},
        {"email": "ben@x.com", "role": "coordinator"},
        {"email": "vera@x.com", "role": "venue"},
    ]

    def test_every_venue_staff_user_and_nobody_else_is_notified(self):
        with patch("app.orchestration.clients.httpx.get", return_value=response(200, self.USERS)), patch(
            "app.orchestration.clients.httpx.post", return_value=response(200)
        ) as post:
            sent = notify_venue_staff("Subject", "Body", "Bearer t")

        self.assertEqual(sent, 2)
        self.assertEqual(
            [c.kwargs["json"] for c in post.call_args_list],
            [
                {"to": "vinod@x.com", "subject": "Subject", "body": "Body"},
                {"to": "vera@x.com", "subject": "Subject", "body": "Body"},
            ],
        )
        self.assertTrue(all(c.args[0].endswith("/notifications") for c in post.call_args_list))
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer t"})

    def test_a_notification_that_fails_is_not_counted_and_the_rest_still_go(self):
        with patch("app.orchestration.clients.httpx.get", return_value=response(200, self.USERS)), patch(
            "app.orchestration.clients.httpx.post", side_effect=[response(500), response(200)]
        ) as post:
            self.assertEqual(notify_venue_staff("S", "B", "Bearer t"), 1)
        self.assertEqual(post.call_count, 2)

    def test_when_venue_staff_cannot_be_listed_or_reached_nothing_is_sent_and_nothing_breaks(self):
        with patch("app.orchestration.clients.httpx.get", return_value=response(503)), patch(
            "app.orchestration.clients.httpx.post"
        ) as post:
            self.assertEqual(notify_venue_staff("S", "B", "Bearer t"), 0)
        post.assert_not_called()
        with patch("app.orchestration.clients.httpx.get", side_effect=httpx.ConnectError("down")):
            self.assertEqual(notify_venue_staff("S", "B", "Bearer t"), 0)

