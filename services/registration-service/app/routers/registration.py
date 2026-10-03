from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.db.session import get_db
from app.schemas.registration import (
    AttendeeOut,
    RegisterRequest,
    RegistrationCountOut,
    RegistrationRosterOut,
)
from app.services.registration_service import RegistrationService
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.openapi import error_responses

router = APIRouter(
    prefix="/registrations",
    tags=["registrations"],
    responses=error_responses(401),
)


def get_registration_service(db: Session = Depends(get_db)) -> RegistrationService:
    return RegistrationService(db, AttendeeRegistrationDAO(db), RegistrationWindowDAO(db))


def _to_attendee(row) -> AttendeeOut:
    return AttendeeOut(
        attendeeRegistrationId=row.attendeeRegistrationId,
        eventId=row.eventId,
        userId=row.userId,
        attendeeName=row.attendeeName,
        attendeeEmail=row.attendeeEmail,
        status=row.status,
        createdAt=row.createdAt,
        withdrawnAt=row.withdrawnAt,
    )


@router.get(
    "/count",
    response_model=RegistrationCountOut,
    summary="Count current registrations",
    description="Number of attendees with status `registered`. Does not return names or other registration details.",
)
def registered_count(
    eventId: str = Query(..., description="Event id, e.g. `e1`."),
    service: RegistrationService = Depends(get_registration_service),
):
    return RegistrationCountOut(count=service.registered_count(eventId))


@router.get(
    "",
    response_model=RegistrationRosterOut,
    summary="List registrations for an event",
    description=(
        "Organiser of the event, or its assigned coordinator. Each row includes the name and email "
        "the attendee supplied, when they registered, and whether they are registered or withdrawn. "
        "The summary includes capacity, currently registered, withdrawn, and places remaining. "
        "Set `includeWithdrawn=false` to leave withdrawn rows out. Other roles are refused. "
        "An attendee receives the places remaining, without other attendees' names. "
        "Not offered when registration is disabled."
    ),
    responses=error_responses(403, 404),
)
def list_registrations(
    eventId: str = Query(..., description="Event id, e.g. `e1`."),
    includeWithdrawn: bool = Query(True, description="Include withdrawn rows. The summary still counts them."),
    authorization: str | None = Depends(forwarded_bearer),
    service: RegistrationService = Depends(get_registration_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    # Attendees can see how many places remain, not the names of other attendees.
    # The organiser and the assigned coordinator still receive the full list.
    if caller.get("role") == "attendee":
        return service.attendee_places(eventId, authorization)
    roster = service.registration_roster(eventId, authorization, includeWithdrawn)
    roster["attendees"] = [_to_attendee(row) for row in roster["attendees"]]
    return roster


@router.get(
    "/mine",
    response_model=list[AttendeeOut],
    summary="List the caller's registrations",
    description="Registrations owned by the signed-in user, including withdrawn ones. The rows are kept.",
)
def my_registrations(
    authorization: str | None = Depends(forwarded_bearer),
    service: RegistrationService = Depends(get_registration_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    rows = service.list_owned(caller.get("userId"), caller.get("email"))
    return [_to_attendee(row) for row in rows]


@router.get(
    "/{registration_id}",
    response_model=AttendeeOut,
    summary="Read one registration",
    description="The attendee who owns the registration. Withdrawn rows are still returned.",
    responses=error_responses(403, 404),
)
def get_registration(
    registration_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: RegistrationService = Depends(get_registration_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return _to_attendee(service.get_for_caller(registration_id, caller))


@router.post(
    "/{registration_id}/withdraw",
    response_model=AttendeeOut,
    summary="Withdraw a registration",
    description=(
        "The owning attendee can withdraw while the event has not started and has not been "
        "completed or cancelled. The row is kept with status `withdrawn` and the place is released."
    ),
    responses=error_responses(403, 404, 409),
)
def withdraw_registration(
    registration_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: RegistrationService = Depends(get_registration_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return _to_attendee(service.withdraw_for_caller(registration_id, caller, authorization))


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
    caller = resolve_caller(authorization, settings.user_service_url)
    row = service.register(body.eventId, body.name, body.email, caller.get("userId"), authorization)
    return _to_attendee(row)
