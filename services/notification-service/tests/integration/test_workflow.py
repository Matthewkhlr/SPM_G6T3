"""In-app notification write and read over HTTP and SQL."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase

CALLER = {"userId": "u5", "role": "attendee", "email": "amy@example.com"}


class TestNotificationWorkflow(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.notification.resolve_caller", return_value=CALLER)
        self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_a_notification_is_stored_and_listed(self):
        gate = app.dependency_overrides.pop(require_authenticated_user)
        self.assertEqual(self.client.get("/notifications").status_code, 401)
        app.dependency_overrides[require_authenticated_user] = gate
        created = self.client.post(
            "/notifications/records",
            headers=self.headers,
            json={"eventId": "e1", "type": "event.changed", "title": "Date moved", "body": "The start time changed."},
        )
        self.assertEqual(created.status_code, 201)
        listed = self.client.get("/notifications", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(listed.json())
