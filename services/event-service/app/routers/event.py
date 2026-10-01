from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_dao import EventDAO
from app.dao.event_field_change_dao import EventFieldChangeDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.db.session import get_db
from app.orchestration.clients import current_organiser, current_technical_support
from app.schemas.event import (
    CoordinatorCandidateOut,
    EventActivityOut,
    EventAssignmentCreate,
    EventAssignmentOut,
    EventCoordinatorOut,
    EventCreate,
    EventDecision,
    EventDraftUpsert,
    EventInternalNotesOut,
    EventOut,
    EventUpdate,
    EventUpdateOut,
    RegistrationAccessOut,
    SignificantFieldsOut,
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
    return EventService(
        db, EventDAO(db), EventAssignmentDAO(db), EventStatusHistoryDAO(db), EventFieldChangeDAO(db)
    )


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
    description="Coordinator only. Submitted / under-review / changes-requested events, ordered by "
    "submission time - longest-waiting first, unless `sort=proposedStartAt`. Pass `assignedTo` "
    "(a coordinator userId) to see only that coordinator's own assignments.",
    responses=error_responses(403, 503),
)
def list_submission_queue(
    sort: str | None = Query(default=None, description="`proposedStartAt` to sort by event date instead of wait time."),
    assignedTo: str | None = Query(default=None, description="Coordinator userId - only their assigned events."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.list_submission_queue(authorization, sort=sort, assigned_to=assignedTo)


@router.get(
    "/mine",
    response_model=list[EventOut],
    summary="My events",
    description="Organiser only. Every event the caller organises, at any stage, except ones they discarded.",
    responses=error_responses(403),
)
def list_my_events(
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    organiser = current_organiser(authorization)
    return service.list_my_events(organiser["userId"], authorization)


@router.get(
    "/significant-fields",
    response_model=SignificantFieldsOut,
    summary="Significant event fields",
    description="Fields whose edit can invalidate a venue booking or equipment reservation (SPM-71 AC2), "
    "and the fields that save without warning (AC1).",
)
def get_significant_fields():
    return EventService.significant_fields()


@router.get(
    "/coordinators",
    response_model=list[CoordinatorCandidateOut],
    summary="Coordinators who can be assigned",
    description="Coordinator only (SPM-66 AC2). Every Event Coordinator with their count of active events, "
    "for information only; no workload limit applies. 503 when user-service cannot be reached.",
    responses=error_responses(403, 503),
)
def list_coordinator_candidates(
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.list_coordinator_candidates(authorization)


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


@router.get(
    "/{event_id}/registration-access",
    response_model=RegistrationAccessOut,
    summary="Registration list access",
    description=(
        "Organiser of this event, or its assigned coordinator. Returns capacity and the "
        "registration period. Refused for every other role. Not offered when registration is disabled."
    ),
    responses=error_responses(403, 404),
)
def registration_access(
    event_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return service.registration_access(event_id, caller)


@router.patch(
    "/{event_id}",
    response_model=EventUpdateOut,
    summary="Update event",
    description="Assigned coordinator only (SPM-71). Send only the fields that change. Name, description, "
    "purpose, category, internal notes, and organiser contact save without warning. A change to a "
    "significant field (see `/events/significant-fields`) on an event with a confirmed venue booking or "
    "equipment reservation, or on a confirmed event, returns 409 naming what is affected until "
    "`confirmSignificantChange` is true; the save then marks those arrangements for re-verification "
    "and a confirmed event becomes `reconsidering`. Completed, cancelled, and rejected events cannot "
    "be edited. 503 when the arrangements cannot be checked; nothing is saved then.",
    responses=error_responses(403, 404, 409, 503),
)
def update_event(
    body: EventUpdate,
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.update_event(event_id, body, caller["userId"], authorization)


@router.get(
    "/{event_id}/coordinator",
    response_model=EventCoordinatorOut,
    summary="Event coordinator contact",
    description="SPM-66 AC5. The assigned coordinator's name and email; all null while unassigned. "
    "Organisers see it for their own organisation's events, staff for any event; attendees get 403.",
    responses=error_responses(403, 404, 503),
)
def get_event_coordinator(
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return service.get_event_coordinator(event_id, caller, authorization)


@router.get(
    "/{event_id}/internal-notes",
    response_model=EventInternalNotesOut,
    summary="Internal notes",
    description="Coordinator only. Staff notes are left out of every event read organisers and attendees can make.",
    responses=error_responses(403, 404, 503),
)
def get_internal_notes(
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.get_internal_notes(event_id)


@router.delete(
    "/{event_id}",
    response_model=EventOut,
    summary="Discard a draft",
    description="Organiser only, and only while the event is still a draft. Once submitted, an event "
    "can no longer be discarded - it moves forward via approve/reject instead.",
    responses=error_responses(403, 404),
)
def discard_event(
    event_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    organiser = current_organiser(authorization)
    return service.discard_draft(event_id, organiser["userId"], authorization)


@router.get(
    "/{event_id}/activity-log",
    response_model=list[EventActivityOut],
    summary="Event activity log",
    description="Every recorded status change (`kind: status`) and field edit (`kind: edit`, with the "
    "field and its previous and new values) for this event, with who made it and when. Oldest first.",
    responses=error_responses(404),
)
def get_activity_log(
    event_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    return service.get_activity_log(event_id, authorization)


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
    description="Coordinator only (SPM-66). Assigns or reassigns the event to an Event Coordinator (422 for "
    "anyone else); no workload limit applies. Writes an `event_assignments` row, shown in the activity log, "
    "and sets `events.coordinator_id`. A `submitted` event moves to `under review`. The coordinator and the "
    "organiser are emailed (best effort). 409 for a completed, cancelled, rejected, draft, or discarded event; "
    "503 when user-service cannot be reached.",
    responses=error_responses(403, 404, 409, 422, 503),
)
def assign_coordinator(
    body: EventAssignmentCreate,
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.assign_coordinator(event_id, body, caller["userId"], authorization)
