from datetime import datetime

from app.models.notification import Notification
from app.routers.notification import NotifyOut, NotifyRequest
from app.services.notifier import send_email
from shared.testing.cases import ServiceTestCase


class TestNotificationService(ServiceTestCase):
    def test_session_dependency_closes(self):
        self.close_db_dependency()

    def test_send_email_queues_the_message(self):
        queued = send_email("amy@connectsphere.com", "Confirmed", "Your event is confirmed.")

        self.assertEqual(queued, {"channel": "email", "to": "amy@connectsphere.com", "status": "queued"})

    def test_notification_row_can_be_stored(self):
        row = Notification(
            notificationId="n-1",
            userId="u-1",
            eventId="e-1",
            type="event-confirmed",
            title="Confirmed",
            body="Your event is confirmed.",
            isRead=False,
            createdAt=datetime.utcnow(),
        )
        self.db.add(row)
        self.db.commit()

        stored = self.db.get(Notification, "n-1")

        self.assertEqual(stored.title, "Confirmed")
        self.assertFalse(stored.isRead)

    def test_request_and_response_models_accept_the_documented_fields(self):
        request = NotifyRequest(to="amy@connectsphere.com", subject="Confirmed", body="Open.")
        response = NotifyOut(channel="email", to=request.to, status="queued")

        self.assertEqual(response.status, "queued")
