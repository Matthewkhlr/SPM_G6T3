"""Registration count and the caller's own list over HTTP and SQL."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase


class TestRegistrationWorkflow(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch(
            "app.routers.registration.resolve_caller",
            return_value={"userId": "u5", "role": "attendee", "email": "amy@example.com"},
        )
        self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_count_and_my_registrations(self):
        gate = app.dependency_overrides.pop(require_authenticated_user)
        self.assertEqual(self.client.get("/registrations/mine").status_code, 401)
        app.dependency_overrides[require_authenticated_user] = gate
        counted = self.client.get("/registrations/count", params={"eventId": "e1"})
        self.assertEqual(counted.status_code, 200)
        self.assertEqual(counted.json()["count"], 0)
        mine = self.client.get("/registrations/me", headers={"Authorization": "Bearer token"})
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.json(), [])
