import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.clients import fetch_event_facts
from app.schemas.venue import EventFacts, SuitabilityRequest
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, VenueCase, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

EVENT = EventFacts(
    expectedAttendance=500,
    layoutPreference="Theatre",
    proposedStartAt=datetime(2030, 1, 7, 10),
    proposedEndAt=datetime(2030, 1, 7, 12),
)


def event_service_returns(status_code, body=None):
    response = MagicMock(status_code=status_code)
    response.json.return_value = body
    return patch("app.orchestration.clients.httpx.get", return_value=response)


class TestFetchEventFacts(unittest.TestCase):
    def test_reads_the_event_from_event_service_forwarding_the_callers_token(self):
        body = {"eventId": "e1", "expectedAttendance": 120, "layoutPreference": "Theatre", "status": "confirmed"}
        with event_service_returns(200, body) as get:
            facts = fetch_event_facts("e1", "Bearer token")

        self.assertEqual((facts.expectedAttendance, facts.layoutPreference), (120, "Theatre"))
        self.assertTrue(get.call_args.args[0].endswith("/events/e1"))
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer token"})

    def test_an_unknown_event_is_not_found(self):
        with event_service_returns(404), self.assertRaises(HTTPException) as ctx:
            fetch_event_facts("nope", "Bearer token")

        self.assertEqual((ctx.exception.status_code, ctx.exception.detail), (404, "Event not found"))

    def test_event_service_errors_and_outages_are_reported_in_plain_words(self):
        failures = [
            event_service_returns(500),
            patch("app.orchestration.clients.httpx.get", side_effect=httpx.ConnectError("refused")),
        ]
        for failure in failures:
            with self.subTest(failure=failure), failure, self.assertRaises(HTTPException) as ctx:
                fetch_event_facts("e1", "Bearer token")

            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("could not be loaded right now", ctx.exception.detail)


class TestSuitabilityRoute(VenueCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        self.venue_id = self.service.create_venue(venue_create(), CALLER).venueId
        self.event = patch("app.routers.venue.fetch_event_facts", return_value=EVENT)
        self.fetch = self.event.start()

    def tearDown(self):
        self.event.stop()
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def post(self, role, **body):
        with signed_in_as(role):
            return self.client.post(
                "/venues/suitability", headers=HEADERS, json={"eventId": "e1", "venueId": self.venue_id, **body}
            )

    def test_coordinators_and_venue_staff_get_the_same_verdict_as_the_shared_rule(self):
        expected = self.service.check_suitability(SuitabilityRequest(eventId="e1", venueId=self.venue_id), EVENT)

        for role in ("coordinator", "venue"):
            with self.subTest(role=role):
                response = self.post(role)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), expected.model_dump(mode="json"))

        self.assertEqual(expected.verdict, "not suitable")
        self.fetch.assert_called_with("e1", HEADERS["Authorization"])

    def test_request_values_override_the_event_record(self):
        response = self.post("coordinator", expectedAttendance=10, layout="Classroom", startsAt="2030-01-07T09:00:00Z")

        self.assertEqual(response.json()["verdict"], "suitable")

    def test_other_roles_cannot_run_the_check(self):
        for role in ("techsupport", "organiser", "attendee"):
            with self.subTest(role=role):
                self.assertEqual(self.post(role).status_code, 403)

    def test_a_negative_attendance_is_rejected(self):
        self.assertEqual(self.post("coordinator", expectedAttendance=-1).status_code, 422)
