from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.services.notifier import send_email
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


@router.post(
    "",
    response_model=NotifyOut,
    summary="Queue an email notification",
    description="Currently a stub: logs the payload and returns `status: queued`. No message is sent.",
)
def notify(body: NotifyRequest):
    return send_email(body.to, body.subject, body.body)
