from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.orchestration.clients import current_organiser, current_technical_support
from app.schemas.event import EventAssignmentCreate, EventAssignmentOut, EventCreate, EventOut
from app.services import event_service
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.openapi import error_responses

router = APIRouter(
    prefix="/events",
    tags=["events"],
    responses=error_responses(401),
)


@router.get(
    "",
    response_model=list[EventOut],
    summary="List events",
    description="Every event, including rejected ones. `registeredCount` is fetched from registration-service.",
)
def list_events(db: Session = Depends(get_db)):
    return event_service.list_events(db)


@router.post(
    "",
    response_model=EventOut,
    status_code=201,
    summary="Create event",
    description="Organiser only. `organiserId` / `organisationId` come from the bearer token. New events start at status `created`.",
    responses=error_responses(403, 503),
)
def create_event(
    body: EventCreate,
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    organiser = current_organiser(authorization)
    return event_service.create_event(
        db, body, organiser["userId"], organiser.get("organisationId")
    )


@router.get(
    "/upcoming/technical",
    response_model=list[EventOut],
    summary="Upcoming events (technical support)",
    description="Technical support only. Events whose `proposedEndAt` is still in the future, excluding `rejected`, `cancelled`, and `completed`.",
    responses=error_responses(403, 503),
)
def list_upcoming_events_for_technical_support(
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    _technical_user = current_technical_support(authorization)
    return event_service.list_upcoming_events(db)


@router.get(
    "/all",
    response_model=list[EventOut],
    summary="List events except rejected",
    description="Same as list events, but omits status `rejected`. Ordered by `proposedStartAt`.",
)
def list_all_events(db: Session = Depends(get_db)):
    return event_service.list_all_events(db)


@router.get(
    "/confirmed",
    response_model=list[EventOut],
    summary="List confirmed events",
    description="Only events with status `confirmed`, ordered by `proposedStartAt`.",
)
def list_confirmed_events(db: Session = Depends(get_db)):
    return event_service.list_confirmed_events(db)


@router.get(
    "/{event_id}",
    response_model=EventOut,
    summary="Get event",
    description="Single event plus live `registeredCount` from registration-service.",
    responses=error_responses(404),
)
def get_event(
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    db: Session = Depends(get_db),
):
    return event_service.get_event(db, event_id)


@router.post(
    "/{event_id}/assign-coordinator",
    response_model=EventAssignmentOut,
    status_code=201,
    summary="Assign coordinator",
    description="Coordinator only. Writes an `event_assignments` row and sets `events.coordinator_id`.",
    responses=error_responses(403, 404, 503),
)
def assign_coordinator(
    body: EventAssignmentCreate,
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return event_service.assign_coordinator(db, event_id, body, caller["userId"])
