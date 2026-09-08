from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.registration import AttendeeOut, RegisterRequest
from app.services import registration_service

router = APIRouter(prefix="/registrations", tags=["registrations"])


@router.get("", response_model=list[AttendeeOut])
def list_registrations(eventId: str, db: Session = Depends(get_db)):
    rows = registration_service.list_for_event(db, eventId)
    return [
        AttendeeOut(
            attendeeRegistrationId=row.attendeeRegistrationId,
            eventId=row.eventId,
            attendeeName=row.attendeeName,
            attendeeEmail=row.attendeeEmail,
        )
        for row in rows
    ]


@router.post("", response_model=AttendeeOut, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    row = registration_service.register(db, body.eventId, body.name, body.email, None)
    return AttendeeOut(
        attendeeRegistrationId=row.attendeeRegistrationId,
        eventId=row.eventId,
        attendeeName=row.attendeeName,
        attendeeEmail=row.attendeeEmail,
    )
