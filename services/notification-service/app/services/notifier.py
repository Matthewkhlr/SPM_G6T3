from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.notification import Notification

# A page large enough that no existing caller that ignores pagination notices
# a behaviour change, while still bounding a single query.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def send_email(to: str, subject: str, body: str) -> dict:
    print(f"[email] to={to} subject={subject} body={body}")
    return {"channel": "email", "to": to, "status": "queued"}


def _new_row(user_id: str, event_id: str | None, type_: str, title: str, body: str) -> Notification:
    return Notification(
        notificationId=str(uuid4()),
        userId=user_id,
        eventId=event_id,
        type=type_,
        title=title,
        body=body,
        isRead=False,
        createdAt=datetime.utcnow(),
    )


def record_notification(db: Session, user_id: str, event_id: str | None, type_: str, title: str, body: str) -> Notification:
    """Add a notification for a user. The caller commits."""
    row = _new_row(user_id, event_id, type_, title, body)
    db.add(row)
    return row


def record_notifications_batch(db: Session, items: list[dict]) -> list[Notification]:
    """Add one notification per item in a single round trip.

    This is the fix for the N-sequential-HTTP-calls shape: a caller fanning a
    trigger out to many recipients (e.g. every registered attendee) sends one
    request with the whole recipient list instead of one request per
    recipient, and this does one bulk `add_all` instead of N individual
    inserts. The caller still commits once, same as record_notification.
    """
    rows = [
        _new_row(item["userId"], item.get("eventId"), item["type"], item["title"], item["body"])
        for item in items
    ]
    db.add_all(rows)
    return rows


def list_for_user(
    db: Session,
    user_id: str,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[Notification]:
    query = db.query(Notification).filter(Notification.userId == user_id)
    if unread_only:
        query = query.filter(Notification.isRead.is_(False))
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    return (
        query.order_by(Notification.createdAt.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def count_unread(db: Session, user_id: str) -> int:
    return (
        db.query(Notification)
        .filter(Notification.userId == user_id, Notification.isRead.is_(False))
        .count()
    )


def mark_read(db: Session, user_id: str, notification_id: str) -> Notification | None:
    """Marks one of the caller's own notifications read. Returns None if it
    doesn't exist or belongs to someone else, so the router can 404 either way
    without telling an attacker which case it was."""
    row = (
        db.query(Notification)
        .filter(Notification.notificationId == notification_id, Notification.userId == user_id)
        .first()
    )
    if row is None:
        return None
    row.isRead = True
    return row


def mark_all_read(db: Session, user_id: str) -> int:
    """Returns how many rows were newly marked read (already-read rows don't count)."""
    updated = (
        db.query(Notification)
        .filter(Notification.userId == user_id, Notification.isRead.is_(False))
        .update({"isRead": True}, synchronize_session=False)
    )
    return updated
