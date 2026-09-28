from app.models.notification import Notification
from app.services import notifier
from shared.testing.cases import ServiceTestCase


class TestNotificationRecords(ServiceTestCase):
    def test_record_notification_stores_a_row_for_the_recipient(self):
        self.assertTrue(
            hasattr(notifier, "record_notification"),
            "record_notification is not implemented",
        )

        stored = notifier.record_notification(
            self.db,
            user_id="u-coord",
            event_id="e1",
            type_="change-response",
            title="Organiser replied",
            body="The capacity is now 80.",
        )
        self.db.commit()

        row = self.db.get(Notification, stored.notificationId)
        self.assertEqual(row.userId, "u-coord")
        self.assertEqual(row.eventId, "e1")
        self.assertIn("capacity is now 80", row.body)
        self.assertFalse(row.isRead)
