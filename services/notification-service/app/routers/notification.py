from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.notifier import list_for_user, record_notification, send_email
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.exceptions.http import forbidden
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
    description="Notifications stored for the signed-in user, newest first. Other users' rows are not included.",
)
def list_notifications(
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return list_for_user(db, caller["userId"])


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
    "",
    response_model=NotifyOut,
    summary="Queue an email notification",
    description="Currently a stub: logs the payload and returns `status: queued`. No message is sent.",
)
def notify(body: NotifyRequest):
    return send_email(body.to, body.subject, body.body)
