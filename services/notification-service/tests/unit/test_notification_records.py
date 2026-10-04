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

    def test_list_for_user_unread_only_excludes_read_rows(self):
        unread = notifier.record_notification(self.db, "u-amy", "e1", "event.cancelled", "Cancelled", "e1 cancelled.")
        read = notifier.record_notification(self.db, "u-amy", "e2", "event.cancelled", "Cancelled", "e2 cancelled.")
        read.isRead = True
        self.db.commit()

        only_unread = notifier.list_for_user(self.db, "u-amy", unread_only=True)

        self.assertEqual([row.notificationId for row in only_unread], [unread.notificationId])

    def test_list_for_user_paginates(self):
        rows = [
            notifier.record_notification(self.db, "u-amy", None, "t", f"Title {i}", "body")
            for i in range(5)
        ]
        for index, row in enumerate(rows):
            row.createdAt = datetime(2026, 1, 1, 9, index)
        self.db.commit()
        # Newest (highest index) first.
        expected_newest_first = list(reversed([row.notificationId for row in rows]))

        page_one = notifier.list_for_user(self.db, "u-amy", page=1, page_size=2)
        page_two = notifier.list_for_user(self.db, "u-amy", page=2, page_size=2)

        self.assertEqual([row.notificationId for row in page_one], expected_newest_first[0:2])
        self.assertEqual([row.notificationId for row in page_two], expected_newest_first[2:4])

    def test_count_unread_counts_only_this_user_s_unread_rows(self):
        notifier.record_notification(self.db, "u-amy", None, "t", "Title", "body")
        read = notifier.record_notification(self.db, "u-amy", None, "t", "Title", "body")
        read.isRead = True
        notifier.record_notification(self.db, "u-other", None, "t", "Title", "body")
        self.db.commit()

        self.assertEqual(notifier.count_unread(self.db, "u-amy"), 1)
        self.assertEqual(notifier.count_unread(self.db, "u-nobody"), 0)

    def test_mark_read_only_affects_the_owner_s_row(self):
        mine = notifier.record_notification(self.db, "u-amy", None, "t", "Title", "body")
        someone_else_s = notifier.record_notification(self.db, "u-other", None, "t", "Title", "body")
        self.db.commit()

        updated = notifier.mark_read(self.db, "u-amy", mine.notificationId)
        missing = notifier.mark_read(self.db, "u-amy", someone_else_s.notificationId)
        unknown = notifier.mark_read(self.db, "u-amy", "no-such-id")
        self.db.commit()

        self.assertIs(updated, mine)
        self.assertTrue(mine.isRead)
        self.assertIsNone(missing)
        self.assertIsNone(unknown)
        self.assertFalse(self.db.get(notifier.Notification, someone_else_s.notificationId).isRead)

    def test_mark_all_read_updates_only_this_user_s_unread_rows_and_counts_them(self):
        first = notifier.record_notification(self.db, "u-amy", None, "t", "Title", "body")
        second = notifier.record_notification(self.db, "u-amy", None, "t", "Title", "body")
        already_read = notifier.record_notification(self.db, "u-amy", None, "t", "Title", "body")
        already_read.isRead = True
        other_user = notifier.record_notification(self.db, "u-other", None, "t", "Title", "body")
        self.db.commit()

        updated = notifier.mark_all_read(self.db, "u-amy")
        self.db.commit()

        self.assertEqual(updated, 2)
        self.assertTrue(self.db.get(notifier.Notification, first.notificationId).isRead)
        self.assertTrue(self.db.get(notifier.Notification, second.notificationId).isRead)
        self.assertFalse(self.db.get(notifier.Notification, other_user.notificationId).isRead)

    def test_record_notifications_batch_adds_one_row_per_item_in_one_call(self):
        items = [
            {"userId": "u5", "eventId": "e1", "type": "event.cancelled", "title": "Cancelled", "body": "For u5."},
            {"userId": "u6", "eventId": "e1", "type": "event.cancelled", "title": "Cancelled", "body": "For u6."},
            {"userId": "u7", "eventId": "e1", "type": "event.cancelled", "title": "Cancelled", "body": "For u7."},
        ]

        rows = notifier.record_notifications_batch(self.db, items)
        self.db.commit()

        self.assertEqual(len(rows), 3)
        self.assertEqual({row.userId for row in rows}, {"u5", "u6", "u7"})
        self.assertEqual(len({row.notificationId for row in rows}), 3, "each row gets its own id")
        for row in rows:
            self.assertEqual(self.db.get(notifier.Notification, row.notificationId).eventId, "e1")
