from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.db.session import get_db
from app.schemas.registration import AttendeeOut, RegisterRequest
from app.services.registration_service import RegistrationService
from shared.auth.deps import forwarded_bearer
from shared.openapi import error_responses

router = APIRouter(
    prefix="/registrations",
    tags=["registrations"],
    responses=error_responses(401),
)


def get_registration_service(db: Session = Depends(get_db)) -> RegistrationService:
    return RegistrationService(db, AttendeeRegistrationDAO(db), RegistrationWindowDAO(db))


@router.get(
    "",
    response_model=list[AttendeeOut],
    summary="List registrations for an event",
    description="Attendees with status `registered` for the given event.",
)
def list_registrations(
    eventId: str = Query(..., description="Event id, e.g. `e1`."),
    service: RegistrationService = Depends(get_registration_service),
):
    rows = service.list_for_event(eventId)
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
def register(
    body: RegisterRequest,
    authorization: str | None = Depends(forwarded_bearer),
    service: RegistrationService = Depends(get_registration_service),
):
    row = service.register(body.eventId, body.name, body.email, None, authorization)
    return AttendeeOut(
        attendeeRegistrationId=row.attendeeRegistrationId,
        eventId=row.eventId,
        attendeeName=row.attendeeName,
        attendeeEmail=row.attendeeEmail,
    )
