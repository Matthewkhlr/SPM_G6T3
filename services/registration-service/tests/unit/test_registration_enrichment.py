from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.models.attendee_registration import AttendeeRegistration
from app.routers.registration import _enrich, _event_card
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase


def _row(**overrides):
    data = dict(
        attendeeRegistrationId="r1",
        eventId="e1",
        userId="u5",
        attendeeName="Amy Wong",
        attendeeEmail="amy@example.com",
        status="registered",
        createdAt=datetime(2026, 9, 1, 9, 0),
    )
    data.update(overrides)
    return AttendeeRegistration(**data)


class TestRegistrationEnrichment(ServiceTestCase):
    def test_a_card_adds_the_event_and_a_missing_card_leaves_the_row_alone(self):
        card = {
            "eventName": "AI in Events Summit",
            "status": "cancelled",
            "proposedStartAt": "2026-11-01T09:00:00",
            "proposedEndAt": "2026-11-01T17:00:00",
            "startsAt": "2026-11-01T09:00:00",
            "endsAt": "2026-11-01T17:00:00",
            "venueName": "Marina Hall A",
            "venueLocation": "HarbourFront Centre",
            "changedAt": "2026-10-01T00:00:00",
        }
        ok = MagicMock(status_code=200)
        ok.json.return_value = card
        with patch("app.routers.registration.httpx.get", return_value=ok):
            enriched = _enrich(_row(), "Bearer token")
        self.assertEqual(enriched.eventName, "AI in Events Summit")
        self.assertTrue(enriched.cancelled)
        self.assertTrue(enriched.changed)
        self.assertEqual(enriched.venueName, "Marina Hall A")
        self.assertIsNotNone(enriched.startsAt)

        earlier = dict(card, changedAt="2026-08-01T00:00:00", status="confirmed")
        ok.json.return_value = earlier
        with patch("app.routers.registration.httpx.get", return_value=ok):
            quiet = _enrich(_row(), "Bearer token")
        self.assertFalse(quiet.changed)
        self.assertFalse(quiet.cancelled)

        aware = _row(createdAt=datetime(2026, 9, 1, tzinfo=timezone.utc))
        ok.json.return_value = dict(earlier, changedAt=datetime(2026, 10, 1, tzinfo=timezone.utc), proposedStartAt=datetime(2026, 11, 1))
        with patch("app.routers.registration.httpx.get", return_value=ok):
            _enrich(aware, "Bearer token")

        broken = dict(card, proposedStartAt="not-a-date", startsAt=None, endsAt=None, proposedEndAt=None, changedAt=None)
        ok.json.return_value = broken
        with patch("app.routers.registration.httpx.get", return_value=ok):
            plain = _enrich(_row(createdAt=None), "Bearer token")
        self.assertIsNone(plain.proposedStartAt)
        self.assertFalse(plain.changed)

        self.assertIsNone(_event_card("e1", None))
        failed = MagicMock(status_code=503)
        with patch("app.routers.registration.httpx.get", return_value=failed):
            self.assertEqual(_enrich(_row(), "Bearer token").eventName, "")
        with patch("app.routers.registration.httpx.get", side_effect=httpx.HTTPError("down")):
            self.assertEqual(_enrich(_row(), "Bearer token").eventName, "")

    def test_me_uses_the_same_list_as_mine(self):
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        caller = patch("app.routers.registration.resolve_caller", return_value={"userId": "u5", "role": "attendee", "email": "amy@example.com"})
        caller.start()
        client = TestClient(app)
        client.__enter__()
        try:
            response = client.get("/registrations/me", headers={"Authorization": "Bearer token"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), [])
        finally:
            client.__exit__(None, None, None)
            caller.stop()
            app.dependency_overrides.clear()
