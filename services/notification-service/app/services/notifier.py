from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.notification import Notification


def send_email(to: str, subject: str, body: str) -> dict:
    print(f"[email] to={to} subject={subject} body={body}")
    return {"channel": "email", "to": to, "status": "queued"}


def record_notification(db: Session, user_id: str, event_id: str | None, type_: str, title: str, body: str) -> Notification:
    """Add a notification for a user. The caller commits."""
    row = Notification(
        notificationId=str(uuid4()),
        userId=user_id,
        eventId=event_id,
        type=type_,
        title=title,
        body=body,
        isRead=False,
        createdAt=datetime.utcnow(),
    )
    db.add(row)
    return row


def list_for_user(db: Session, user_id: str) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.userId == user_id)
        .order_by(Notification.createdAt.desc())
        .all()
    )
