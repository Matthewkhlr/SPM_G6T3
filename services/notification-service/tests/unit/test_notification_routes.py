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

    def test_staff_can_batch_notify_several_recipients_in_one_call(self):
        self.resolve_caller.return_value = {"userId": "u-ben", "role": "coordinator"}

        created = self.client.post(
            "/notifications/records/batch",
            headers={"Authorization": "Bearer token"},
            json={
                "items": [
                    {"userId": "u5", "eventId": "e1", "type": "event.cancelled", "title": "Cancelled", "body": "For u5."},
                    {"userId": "u6", "eventId": "e1", "type": "event.cancelled", "title": "Cancelled", "body": "For u6."},
                ]
            },
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual({row["userId"] for row in created.json()}, {"u5", "u6"})
        self.assertEqual(self.db.query(Notification).filter(Notification.eventId == "e1").count(), 2)

    def test_batch_is_rejected_whole_when_any_item_is_not_staff_allowed(self):
        self.resolve_caller.return_value = {"userId": "u-amy", "role": "organiser"}

        denied = self.client.post(
            "/notifications/records/batch",
            headers={"Authorization": "Bearer token"},
            json={
                "items": [
                    {"userId": "u-amy", "eventId": "e1", "type": "t", "title": "Mine", "body": "ok"},
                    {"userId": "u-other", "eventId": "e1", "type": "t", "title": "Spoofed", "body": "not staff"},
                ]
            },
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.db.query(Notification).count(), 0)

    def test_notify_schedules_the_email_as_a_background_task(self):
        with patch("app.routers.notification.send_email") as mock_send:
            response = self.client.post(
                "/notifications",
                json={"to": "amy@connectsphere.com", "subject": "Confirmed", "body": "Open."},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"channel": "email", "to": "amy@connectsphere.com", "status": "queued"})
        mock_send.assert_called_once_with("amy@connectsphere.com", "Confirmed", "Open.")

    def test_read_one_marks_it_read_and_404s_for_someone_else_s_notification(self):
        mine = self.client.post(
            "/notifications/records",
            headers={"Authorization": "Bearer token"},
            json={"title": "Mine", "body": "For me."},
        ).json()
        self.resolve_caller.return_value = {"userId": "u-other", "role": "attendee"}
        someone_else_s = self.client.post(
            "/notifications/records",
            headers={"Authorization": "Bearer token"},
            json={"title": "Theirs", "body": "For them."},
        ).json()

        self.resolve_caller.return_value = {"userId": "u-amy", "role": "attendee"}
        marked = self.client.post(f"/notifications/{mine['notificationId']}/read", headers={"Authorization": "Bearer token"})
        forbidden_id = self.client.post(
            f"/notifications/{someone_else_s['notificationId']}/read", headers={"Authorization": "Bearer token"}
        )
        unknown_id = self.client.post("/notifications/no-such-id/read", headers={"Authorization": "Bearer token"})

        self.assertEqual(marked.status_code, 200)
        self.assertTrue(marked.json()["isRead"])
        self.assertEqual(forbidden_id.status_code, 404)
        self.assertEqual(unknown_id.status_code, 404)

    def test_read_all_marks_every_one_of_the_caller_s_notifications(self):
        self.client.post(
            "/notifications/records", headers={"Authorization": "Bearer token"}, json={"title": "One", "body": "a"}
        )
        self.client.post(
            "/notifications/records", headers={"Authorization": "Bearer token"}, json={"title": "Two", "body": "b"}
        )

        result = self.client.post("/notifications/read-all", headers={"Authorization": "Bearer token"})
        inbox = self.client.get("/notifications", headers={"Authorization": "Bearer token"})

        self.assertEqual(result.json(), {"updated": 2})
        self.assertTrue(all(row["isRead"] for row in inbox.json()))

    def test_unread_count_reflects_read_state(self):
        self.client.post(
            "/notifications/records", headers={"Authorization": "Bearer token"}, json={"title": "One", "body": "a"}
        )
        created = self.client.post(
            "/notifications/records", headers={"Authorization": "Bearer token"}, json={"title": "Two", "body": "b"}
        ).json()

        before = self.client.get("/notifications/unread-count", headers={"Authorization": "Bearer token"})
        self.client.post(f"/notifications/{created['notificationId']}/read", headers={"Authorization": "Bearer token"})
        after = self.client.get("/notifications/unread-count", headers={"Authorization": "Bearer token"})

        self.assertEqual(before.json(), {"unreadCount": 2})
        self.assertEqual(after.json(), {"unreadCount": 1})

    def test_list_notifications_filters_unread_only_and_paginates(self):
        headers = {"Authorization": "Bearer token"}
        for i in range(3):
            self.client.post("/notifications/records", headers=headers, json={"title": f"T{i}", "body": "b"})
        first_id = self.client.get("/notifications", headers=headers).json()[-1]["notificationId"]
        self.client.post(f"/notifications/{first_id}/read", headers=headers)

        unread_only = self.client.get("/notifications", headers=headers, params={"unreadOnly": True})
        page_one = self.client.get("/notifications", headers=headers, params={"page": 1, "pageSize": 2})
        page_two = self.client.get("/notifications", headers=headers, params={"page": 2, "pageSize": 2})

        self.assertEqual(len(unread_only.json()), 2)
        self.assertEqual(len(page_one.json()), 2)
        self.assertEqual(len(page_two.json()), 1)
