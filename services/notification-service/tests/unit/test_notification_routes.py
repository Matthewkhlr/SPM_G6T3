from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase


class TestNotificationRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1", "email": "amy@connectsphere.com"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_post_notifications_returns_queued(self):
        response = self.client.post(
            "/notifications",
            json={"to": "amy@connectsphere.com", "subject": "Confirmed", "body": "Open."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "queued")
