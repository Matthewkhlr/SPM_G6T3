import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from app.services.registration_service import _event
from tests.unit.support import FakeEventClient, FakeResponse


class TestEventLookup(unittest.TestCase):
    def setUp(self):
        FakeEventClient.response = FakeResponse(200)
        FakeEventClient.error = None
        FakeEventClient.captured = {}

    def test_forwards_the_bearer_token(self):
        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            payload = _event("e1", "Bearer some-real-token")

        self.assertEqual(payload["eventId"], "e1")
        self.assertEqual(FakeEventClient.captured["headers"], {"Authorization": "Bearer some-real-token"})

    def test_sends_no_auth_header_when_none_is_available(self):
        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            _event("e1", None)

        self.assertEqual(FakeEventClient.captured["headers"], {})

    def test_raises_not_found_when_event_service_rejects_the_token(self):
        FakeEventClient.response = FakeResponse(401, {"detail": "Invalid or expired token"})

        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            with self.assertRaises(HTTPException) as ctx:
                _event("e1", "Bearer expired-token")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_raises_not_found_when_event_service_is_unreachable(self):
        FakeEventClient.error = httpx.ConnectError("down")

        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            with self.assertRaises(HTTPException) as ctx:
                _event("e1", "Bearer token")

        self.assertEqual(ctx.exception.status_code, 404)
