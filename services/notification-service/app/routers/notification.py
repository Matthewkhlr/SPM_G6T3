from fastapi import APIRouter
from pydantic import BaseModel

from app.services.notifier import send_email

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotifyRequest(BaseModel):
    to: str
    subject: str
    body: str


@router.post("")
def notify(body: NotifyRequest):
    return send_email(body.to, body.subject, body.body)
