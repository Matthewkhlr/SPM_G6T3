from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.registration import AttendeeOut, RegisterRequest
from app.services import registration_service
from shared.openapi import error_responses

router = APIRouter(
    prefix="/registrations",
    tags=["registrations"],
    responses=error_responses(401),
)


@router.get(
    "",
    response_model=list[AttendeeOut],
    summary="List registrations for an event",
    description="Attendees with status `registered` for the given event.",
)
def list_registrations(
    eventId: str = Query(..., description="Event id, e.g. `e1`."),
    db: Session = Depends(get_db),
):
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


@router.post(
    "",
    response_model=AttendeeOut,
    status_code=201,
    summary="Register an attendee",
    description=(
        "Creates a registration when the event is `confirmed`, registration is enabled and open, "
        "capacity is not exceeded, and the email is not already registered."
    ),
    responses=error_responses(404, 409),
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    row = registration_service.register(db, body.eventId, body.name, body.email, None)
    return AttendeeOut(
        attendeeRegistrationId=row.attendeeRegistrationId,
        eventId=row.eventId,
        attendeeName=row.attendeeName,
        attendeeEmail=row.attendeeEmail,
    )
