from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.notifier import (
    count_unread,
    list_for_user,
    mark_all_read,
    mark_read,
    record_notification,
    record_notifications_batch,
    send_email,
)
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.exceptions.http import forbidden, not_found
from shared.openapi import error_responses

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    responses=error_responses(401),
)


class NotifyRequest(BaseModel):
    to: str = Field(description="Recipient email address.")
    subject: str
    body: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "to": "organiser@connectsphere.com",
                "subject": "AI in Events Summit is confirmed",
                "body": "Your event has been confirmed. Registration is open.",
            }
        }
    )


class NotifyOut(BaseModel):
    channel: str
    to: str
    status: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "channel": "email",
                "to": "organiser@connectsphere.com",
                "status": "queued",
            }
        }
    )


# Internal staff may notify someone else, e.g. a coordinator's change telling
# the organiser and attendees (SPM-90). Everyone else notifies only themselves.
STAFF_ROLES = {"coordinator", "venue", "techsupport"}


class RecordRequest(BaseModel):
    userId: str | None = Field(
        default=None,
        description="Recipient; defaults to the caller. Only staff (coordinator, venue, techsupport) may name someone else.",
    )
    eventId: str | None = None
    type: str = "registration.withdrawn"
    title: str
    body: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "type": "registration.withdrawn",
                "title": "Registration withdrawn",
                "body": "You have withdrawn from AI in Events Summit (e1).",
            }
        }
    )


class RecordItem(BaseModel):
    userId: str = Field(description="Recipient. Unlike the single-record endpoint this is always required.")
    eventId: str | None = None
    type: str
    title: str
    body: str


class RecordBatchRequest(BaseModel):
    """One trigger occurrence fanned out to every recipient it concerns (e.g.
    every registered attendee told an event was cancelled). Sent as a single
    request so the caller does one round trip instead of one per recipient."""

    items: list[RecordItem] = Field(min_length=1, max_length=2000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {"userId": "u5", "eventId": "e1", "type": "event.cancelled", "title": "Event cancelled", "body": "AI in Events Summit (e1) was cancelled."},
                    {"userId": "u6", "eventId": "e1", "type": "event.cancelled", "title": "Event cancelled", "body": "AI in Events Summit (e1) was cancelled."},
                ]
            }
        }
    )


class MarkAllReadOut(BaseModel):
    updated: int


class UnreadCountOut(BaseModel):
    unreadCount: int


class NotificationOut(BaseModel):
    notificationId: str
    userId: str
    eventId: str | None = None
    type: str
    title: str
    body: str
    isRead: bool
    createdAt: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "notificationId": "n1",
                "userId": "u5",
                "eventId": "e1",
                "type": "registration.withdrawn",
                "title": "Registration withdrawn",
                "body": "You have withdrawn from AI in Events Summit (e1).",
                "isRead": False,
                "createdAt": "2026-10-01T09:00:00",
            }
        }
    )


@router.get(
    "",
    response_model=list[NotificationOut],
    summary="List the caller's notifications",
    description="Notifications stored for the signed-in user, newest first, one page at a time. "
    "Other users' rows are not included.",
)
def list_notifications(
    unreadOnly: bool = Query(False, description="Only notifications not yet marked read."),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return list_for_user(db, caller["userId"], unread_only=unreadOnly, page=page, page_size=pageSize)


@router.get(
    "/unread-count",
    response_model=UnreadCountOut,
    summary="Count the caller's unread notifications",
    description="For the shell's notification badge. Cheaper than fetching and counting the full list.",
)
def unread_count(
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return UnreadCountOut(unreadCount=count_unread(db, caller["userId"]))


@router.post(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark one notification read",
    description="Only the caller's own notification. 404 for someone else's or an unknown id, so an id "
    "can't be used to probe whether it exists.",
    responses=error_responses(404),
)
def read_one(
    notification_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    row = mark_read(db, caller["userId"], notification_id)
    if row is None:
        raise not_found("Notification not found")
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/read-all",
    response_model=MarkAllReadOut,
    summary="Mark every one of the caller's notifications read",
)
def read_all(
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    updated = mark_all_read(db, caller["userId"])
    db.commit()
    return MarkAllReadOut(updated=updated)


@router.post(
    "/records",
    response_model=NotificationOut,
    status_code=201,
    summary="Store an in-app notification",
    description="Persists a notification for the caller, or for `userId` when the caller is staff "
    "(coordinator, venue, techsupport). Anyone else naming another user gets 403.",
    responses=error_responses(403),
)
def record(body: RecordRequest, authorization: str | None = Depends(forwarded_bearer), db: Session = Depends(get_db)):
    caller = resolve_caller(authorization, settings.user_service_url)
    recipient = body.userId or caller["userId"]
    if recipient != caller["userId"] and caller.get("role") not in STAFF_ROLES:
        raise forbidden("Only staff can notify another user")
    row = record_notification(db, recipient, body.eventId, body.type, body.title, body.body)
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/records/batch",
    response_model=list[NotificationOut],
    status_code=201,
    summary="Store one notification per recipient in a single call",
    description="For a trigger that fans out to many recipients at once (e.g. every registered attendee "
    "told an event changed). One bulk insert instead of one request per recipient. Every item's `userId` "
    "is checked the same way as the single-record endpoint: naming anyone other than the caller requires "
    "a staff role (coordinator, venue, techsupport), and the whole batch is rejected together if any item "
    "fails that check, so nothing is saved half-done.",
    responses=error_responses(403),
)
def record_batch(
    body: RecordBatchRequest,
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    if caller.get("role") not in STAFF_ROLES:
        for item in body.items:
            if item.userId != caller["userId"]:
                raise forbidden("Only staff can notify another user")
    rows = record_notifications_batch(db, [item.model_dump() for item in body.items])
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


@router.post(
    "",
    response_model=NotifyOut,
    summary="Queue an email notification",
    description="Currently a stub: logs the payload and returns `status: queued`. The send happens after "
    "the response goes out (a FastAPI background task) so a slow or real SMTP call later never adds "
    "latency to whatever action triggered the email.",
)
def notify(body: NotifyRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(send_email, body.to, body.subject, body.body)
    return NotifyOut(channel="email", to=body.to, status="queued")
