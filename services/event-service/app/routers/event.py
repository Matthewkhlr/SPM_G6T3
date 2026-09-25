from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_dao import EventDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.db.session import get_db
from app.orchestration.clients import current_organiser, current_technical_support
from app.schemas.event import (
    EventAssignmentCreate,
    EventAssignmentOut,
    EventCreate,
    EventDecision,
    EventDraftUpsert,
    EventOut,
)
from app.services.event_service import EventService
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.openapi import error_responses

router = APIRouter(
    prefix="/events",
    tags=["events"],
    responses=error_responses(401),
)


def get_event_service(db: Session = Depends(get_db)) -> EventService:
    return EventService(db, EventDAO(db), EventAssignmentDAO(db), EventStatusHistoryDAO(db))


@router.get(
    "",
    response_model=list[EventOut],
    summary="List events",
    description="Every event, including rejected ones. `registeredCount` is fetched from registration-service.",
)
def list_events(
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    return service.list_events(authorization)


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
    service: EventService = Depends(get_event_service),
):
    organiser = current_organiser(authorization)
    return service.create_event(body, organiser["userId"], organiser.get("organisationId"), authorization)

@router.post("/drafts", response_model=EventOut, status_code=201)
def create_draft(
    body: EventDraftUpsert,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    organiser = current_organiser(authorization)
    return service.create_draft(body, organiser["userId"], organiser.get("organisationId"), authorization)


@router.get("/drafts/mine", response_model=list[EventOut])
def list_my_drafts(
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    organiser = current_organiser(authorization)
    return service.list_my_drafts(organiser["userId"], authorization)


@router.put("/{event_id}/draft", response_model=EventOut)
def update_draft(
    event_id: str,
    body: EventDraftUpsert,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    organiser = current_organiser(authorization)
    return service.update_draft(event_id, body, organiser["userId"], authorization)


@router.post("/{event_id}/submit", response_model=EventOut)
def submit_draft(
    event_id: str,
    body: EventCreate,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    organiser = current_organiser(authorization)
    return service.submit_draft(event_id, body, organiser["userId"], authorization)


@router.get("/upcoming/technical", response_model=list[EventOut])
def list_upcoming_events_for_technical_support(
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    _technical_user = current_technical_support(authorization)
    return service.list_upcoming_events(authorization)


@router.get(
    "/all",
    response_model=list[EventOut],
    summary="List events except rejected",
    description="Same as list events, but omits status `rejected`. Ordered by `proposedStartAt`.",
)
def list_all_events(
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    return service.list_all_events(authorization)


@router.get(
    "/confirmed",
    response_model=list[EventOut],
    summary="List confirmed events",
    description="Only events with status `confirmed`, ordered by `proposedStartAt`.",
)
def list_confirmed_events(
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    return service.list_confirmed_events(authorization)


@router.get(
    "/queue",
    response_model=list[EventOut],
    summary="Coordinator review queue",
    description="Coordinator only. Submitted events awaiting review, ordered by submission time - longest-waiting first.",
    responses=error_responses(403, 503),
)
def list_submission_queue(
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.list_submission_queue(authorization)


@router.get(
    "/{event_id}",
    response_model=EventOut,
    summary="Get event",
    description="Single event plus live `registeredCount` from registration-service.",
    responses=error_responses(404),
)
def get_event(
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    return service.get_event(event_id, authorization)


@router.post("/{event_id}/approve", response_model=EventOut)
def approve_event(
    event_id: str,
    body: EventDecision,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.approve_event(event_id, caller["userId"], authorization)


@router.post("/{event_id}/reject", response_model=EventOut)
def reject_event(
    event_id: str,
    body: EventDecision,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.reject_event(event_id, caller["userId"], body.reason or "", authorization)


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
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.assign_coordinator(event_id, body, caller["userId"])
