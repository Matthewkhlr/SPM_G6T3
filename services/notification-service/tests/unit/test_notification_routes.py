from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.notification import Notification
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase


class TestNotificationRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1", "email": "amy@connectsphere.com"}
        self.identity = patch("app.routers.notification.resolve_caller")
        self.resolve_caller = self.identity.start()
        self.resolve_caller.return_value = {"userId": "u-amy", "role": "attendee", "email": "attendee@connectsphere.com"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.identity.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_post_notifications_returns_queued(self):
        response = self.client.post(
            "/notifications",
            json={"to": "amy@connectsphere.com", "subject": "Confirmed", "body": "Open."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "queued")

    def test_a_record_is_stored_for_the_caller_and_listed_back_to_them(self):
        self.db.add(
            Notification(
                notificationId="n-other",
                userId="u-other",
                eventId="e1",
                type="registration.withdrawn",
                title="Secret",
                body="secret-other",
                isRead=False,
            )
        )
        self.db.commit()

        created = self.client.post(
            "/notifications/records",
            headers={"Authorization": "Bearer token"},
            json={
                "eventId": "e1",
                "type": "registration.withdrawn",
                "title": "Registration withdrawn",
                "body": "You have withdrawn from AI in Events Summit (e1).",
            },
        )
        inbox = self.client.get("/notifications", headers={"Authorization": "Bearer token"})

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["userId"], "u-amy")
        self.assertIn("withdrawn", created.json()["body"])
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(len(inbox.json()), 1)
        self.assertIn("e1", inbox.text)
        self.assertNotIn("secret-other", inbox.text)
        self.assertNotIn("n-other", inbox.text)
