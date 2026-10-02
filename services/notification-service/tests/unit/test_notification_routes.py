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

    def test_staff_can_notify_another_user(self):
        self.resolve_caller.return_value = {"userId": "u-ben", "role": "coordinator"}

        created = self.client.post(
            "/notifications/records",
            headers={"Authorization": "Bearer token"},
            json={"userId": "u-amy", "eventId": "e3", "type": "event.registration_settings", "title": "Changed", "body": "Capacity 60."},
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["userId"], "u-amy")
        self.assertEqual(self.db.query(Notification).filter(Notification.userId == "u-amy").count(), 1)

    def test_anyone_else_cannot_notify_another_user(self):
        for role in ("attendee", "organiser"):
            self.resolve_caller.return_value = {"userId": "u-amy", "role": role}
            with self.subTest(role=role):
                denied = self.client.post(
                    "/notifications/records",
                    headers={"Authorization": "Bearer token"},
                    json={"userId": "u-other", "title": "Spoofed", "body": "Not from staff."},
                )
                self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.db.query(Notification).count(), 0)

    def test_naming_yourself_is_allowed_for_anyone(self):
        created = self.client.post(
            "/notifications/records",
            headers={"Authorization": "Bearer token"},
            json={"userId": "u-amy", "title": "Mine", "body": "For me."},
        )

        self.assertEqual((created.status_code, created.json()["userId"]), (201, "u-amy"))
