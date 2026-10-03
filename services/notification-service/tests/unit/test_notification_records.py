from datetime import datetime

from app.models.notification import Notification
from app.services import notifier
from shared.testing.cases import ServiceTestCase


class TestNotificationRecords(ServiceTestCase):
    def test_record_notification_stores_a_row_for_the_recipient(self):
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

    def test_list_for_user_returns_only_that_user_newest_first(self):
        older = notifier.record_notification(
            self.db, "u-amy", "e1", "registration.withdrawn", "Withdrawn", "You have withdrawn from e1."
        )
        newer = notifier.record_notification(
            self.db, "u-amy", "e2", "registration.withdrawn", "Withdrawn", "You have withdrawn from e2."
        )
        other = notifier.record_notification(
            self.db, "u-other", "e1", "registration.withdrawn", "Secret", "secret-other"
        )
        older.createdAt = datetime(2026, 1, 1, 9, 0, 0)
        newer.createdAt = datetime(2026, 1, 2, 9, 0, 0)
        self.db.commit()

        mine = notifier.list_for_user(self.db, "u-amy")
        nobody = notifier.list_for_user(self.db, "u-nobody")

        self.assertEqual([row.notificationId for row in mine], [newer.notificationId, older.notificationId])
        self.assertNotIn(other.notificationId, [row.notificationId for row in mine])
        self.assertNotIn("secret-other", "".join(row.body for row in mine))
        self.assertEqual(nobody, [])
