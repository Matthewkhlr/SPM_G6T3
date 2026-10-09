from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_change_request_dao import EventChangeRequestDAO
from app.dao.event_dao import EventDAO
from app.dao.event_field_change_dao import EventFieldChangeDAO
from app.dao.event_review_dao import EventReviewDAO
from app.dao.event_safety_handoff_dao import EventSafetyHandoffDAO
from app.dao.event_safety_review_dao import EventSafetyReviewDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.db.session import get_db
from app.orchestration.clients import current_organiser, current_technical_support
from app.schemas.event import (
    ChangeableFieldsOut,
    ChangeRequestAccept,
    ChangeRequestCreate,
    ChangeRequestDecline,
    ChangeRequestOut,
    ClarificationCreate,
    ClarificationOut,
    ClarificationReplyCreate,
    ConfirmationOut,
    CoordinatorCandidateOut,
    EventActivityOut,
    EventApproval,
    EventApprovalOut,
    EventAssignmentCreate,
    EventAssignmentOut,
    EventCoordinatorOut,
    EventCreate,
    EventDecision,
    EventIntake,
    EventConfirmOut,
    EventDecisionOut,
    EquipmentNotRequired,
    EventDraftUpsert,
    EventInternalNotesOut,
    EventOut,
    EventUpdate,
    OrganiserDraftPatch,
    RequirementOptionsOut,
    EventUpdateOut,
    RegistrationAccessOut,
    RegistrationSettingsOut,
    RegistrationSettingsUpdate,
    SafetyApproval,
    SafetyChangeRequest,
    SafetyRejection,
    SafetyHandoffOut,
    SafetyReviewOut,
    SafetySubmission,
    SafetyTechnicalHandoff,
    SafetyVenueHandoff,
    SignificantFieldsOut,
)
from app.schemas.followup import OpenEventOut, ReadinessCreate, ReadinessItemOut, ReadinessPatch
from app.services.event_followup import EventFollowUp
from app.services.event_service import EventService
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.openapi import error_responses

router = APIRouter(
    prefix="/events",
    tags=["events"],
    responses=error_responses(401),
)


def get_followup(db: Session = Depends(get_db)) -> EventFollowUp:
    return EventFollowUp(db)


def get_event_service(db: Session = Depends(get_db)) -> EventService:
    return EventService(
        db,
        EventDAO(db),
        EventAssignmentDAO(db),
        EventStatusHistoryDAO(db),
        EventFieldChangeDAO(db),
        EventReviewDAO(db),
        EventChangeRequestDAO(db),
        EventSafetyReviewDAO(db),
        EventSafetyHandoffDAO(db),
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
    body: EventIntake,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    organiser = current_organiser(authorization)
    if body.proposedStartAt is None or body.proposedEndAt is None:
        return service.create_draft(
            body.to_draft(), organiser["userId"], organiser.get("organisationId"), authorization
        )
    return service.create_event(
        body.to_create(), organiser["userId"], organiser.get("organisationId"), authorization
    )

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
async def submit_draft(
    event_id: str,
    request: Request,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    organiser = current_organiser(authorization)
    raw = await request.body()
    if not raw or not raw.strip():
        return service.submit_stored_draft(event_id, organiser["userId"], authorization)
    try:
        body = EventCreate.model_validate_json(raw)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
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
    "/requirement-options",
    response_model=RequirementOptionsOut,
    summary="Published requirement lists",
    description="Layouts, facilities, and accessibility needs an organiser can choose (SPM-80).",
)
def get_requirement_options(service: EventService = Depends(get_event_service)):
    return service.requirement_options()


@router.get(
    "/changeable-fields",
    response_model=ChangeableFieldsOut,
    summary="Fields an organiser can ask to change",
    description="SPM-106 AC3. The fields a change request may propose new values for.",
)
def get_changeable_fields():
    return EventService.changeable_fields()


@router.get(
    "/safety-reviews",
    response_model=list[SafetyReviewOut],
    summary="Safety review queue",
    description="Safety Officers only (SPM-120). Reviews with the given status, longest-waiting first; "
    "`pending` by default.",
    responses=error_responses(403),
)
def list_safety_reviews(
    status: Literal["pending", "approved", "rejected", "changes_requested", "superseded"] = Query(
        default="pending", description="Review status to list."
    ),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"safety"})
    return service.list_safety_reviews(status)


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
    "/open-for-registration",
    response_model=list[OpenEventOut],
    summary="Events an attendee can browse",
)
def list_open_for_registration(
    search: str = Query("", description="Match on the event name."),
    category: str = Query("", description="Category, matched exactly."),
    fromDate: str = Query("", alias="from", description="YYYY-MM-DD. Events starting on or after this date."),
    authorization: str | None = Depends(forwarded_bearer),
    followup: EventFollowUp = Depends(get_followup),
):
    resolve_caller(authorization, settings.user_service_url)
    return followup.list_open(authorization, search, category, fromDate)


@router.get(
    "/open-for-registration/{event_id}",
    response_model=OpenEventOut,
    summary="One event that is open for registration",
    responses=error_responses(404),
)
def get_open_for_registration(
    event_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    followup: EventFollowUp = Depends(get_followup),
):
    resolve_caller(authorization, settings.user_service_url)
    return followup.get_open(event_id, authorization)


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


@router.get("/{event_id}/attendee-card", response_model=OpenEventOut)
def attendee_card(
    event_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    followup: EventFollowUp = Depends(get_followup),
):
    resolve_caller(authorization, settings.user_service_url)
    return followup.attendee_card(event_id, authorization)


@router.get("/{event_id}/readiness", response_model=list[ReadinessItemOut])
def list_readiness(
    event_id: str,
    dueSoon: bool = Query(False),
    authorization: str | None = Depends(forwarded_bearer),
    followup: EventFollowUp = Depends(get_followup),
):
    resolve_caller(
        authorization, settings.user_service_url, allowed_roles={"coordinator", "organiser", "techsupport"}
    )
    return followup.list_readiness(event_id, authorization, dueSoon)


@router.post("/{event_id}/readiness-items", response_model=ReadinessItemOut, status_code=201)
def create_readiness_item(
    event_id: str,
    body: ReadinessCreate,
    authorization: str | None = Depends(forwarded_bearer),
    followup: EventFollowUp = Depends(get_followup),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return followup.create_item(event_id, body, authorization)


@router.get("/{event_id}/readiness-items/{item_id}", response_model=ReadinessItemOut)
def get_readiness_item(
    event_id: str,
    item_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    followup: EventFollowUp = Depends(get_followup),
):
    resolve_caller(
        authorization, settings.user_service_url, allowed_roles={"coordinator", "organiser", "techsupport"}
    )
    return followup.get_item(event_id, item_id)


@router.patch("/{event_id}/readiness-items/{item_id}", response_model=ReadinessItemOut)
def update_readiness_item(
    event_id: str,
    item_id: str,
    body: ReadinessPatch,
    authorization: str | None = Depends(forwarded_bearer),
    followup: EventFollowUp = Depends(get_followup),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return followup.update_item(event_id, item_id, body, authorization)


@router.delete("/{event_id}/readiness-items/{item_id}", status_code=204)
def delete_readiness_item(
    event_id: str,
    item_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    followup: EventFollowUp = Depends(get_followup),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    followup.delete_item(event_id, item_id)


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
async def update_event(
    request: Request,
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    payload = await request.json()
    caller = resolve_caller(authorization, settings.user_service_url)
    if caller.get("role") == "organiser":
        try:
            draft = OrganiserDraftPatch.model_validate(payload)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
        return service.patch_own_draft(event_id, draft, caller["userId"], authorization)
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    try:
        body = EventUpdate.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    return service.update_event(event_id, body, caller["userId"], authorization)


@router.patch(
    "/{event_id}/registration-settings",
    response_model=RegistrationSettingsOut,
    summary="Set registration needed, period, and capacity",
    description="Assigned coordinator only (SPM-90), from `planning` until `confirmed`. Send only the fields "
    "that change. Registration must close after it opens and no later than the event starts (422). A capacity "
    "below the number already registered is 409 naming that number. A capacity above what a confirmed venue "
    "booking holds in the event's layout, or turning registration off while people are registered, is 409 "
    "with `requiresConfirmation` and `warnings` until `confirmOverVenueCapacity` / `confirmRegistrationOff` "
    "is true. Each changed field goes to the activity log; the organiser is notified, and attendees too when "
    "registration is turned off. 503 when registrations or the venue booking cannot be checked; nothing is "
    "saved then.",
    responses=error_responses(403, 404, 409, 503),
)
def update_registration_settings(
    body: RegistrationSettingsUpdate,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.update_registration_settings(event_id, body, caller["userId"], authorization)


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
    "/{event_id}/decision",
    response_model=EventDecisionOut,
    summary="Approval decision",
    description="SPM-69 AC3. The latest decision on the request, with its note, who made it, and when; "
    "all null until one is made. Organisers see it for their own organisation's events, staff for any "
    "event; attendees get 403.",
    responses=error_responses(403, 404, 503),
)
def get_event_decision(
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return service.get_event_decision(event_id, caller)


@router.get(
    "/{event_id}/clarifications",
    response_model=list[ClarificationOut],
    summary="Clarification threads",
    description="SPM-68. Every clarification on the event, oldest first, each with its thread: the question, "
    "then every reply, with author, role, and time. Organisers see them for their own organisation's events, "
    "staff for any event, at any stage; attendees get 403.",
    responses=error_responses(403, 404),
)
def list_clarifications(
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return service.list_clarifications(event_id, caller, authorization)


@router.post(
    "/{event_id}/clarifications",
    response_model=ClarificationOut,
    status_code=201,
    summary="Raise a clarification",
    description="Assigned coordinator only (SPM-68). States what is unclear and optionally the request field it "
    "concerns. Opens a clarification, moves the request to `changes requested`, and emails the organiser (best "
    "effort). Several can be open at once. 409 for a draft, an event with no coordinator, or one past review; "
    "403 for any other coordinator.",
    responses=error_responses(403, 404, 409),
)
def raise_clarification(
    body: ClarificationCreate,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.raise_clarification(event_id, body, caller["userId"], authorization)


@router.post(
    "/{event_id}/clarifications/{clarification_id}/reply",
    response_model=ClarificationOut,
    status_code=201,
    summary="Reply to a clarification",
    description="The event's organiser (or a colleague in their organisation) or its assigned coordinator "
    "(SPM-68 AC3). Returns the whole thread. The other side is emailed (best effort). 409 once the "
    "clarification is resolved.",
    responses=error_responses(403, 404, 409),
)
def reply_to_clarification(
    body: ClarificationReplyCreate,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    clarification_id: str = Path(..., description="Clarification id, e.g. `rv-clarify-e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"organiser", "coordinator"})
    return service.reply_to_clarification(event_id, clarification_id, body, caller, authorization)


@router.post(
    "/{event_id}/clarifications/{clarification_id}/resolve",
    response_model=ClarificationOut,
    summary="Resolve a clarification",
    description="Assigned coordinator only (SPM-68 AC5). Once no clarification is open, a `changes requested` "
    "request returns to `under review`. 409 if it is already resolved.",
    responses=error_responses(403, 404, 409),
)
def resolve_clarification(
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    clarification_id: str = Path(..., description="Clarification id, e.g. `rv-clarify-e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.resolve_clarification(event_id, clarification_id, caller["userId"], authorization)


@router.post(
    "/{event_id}/safety-reviews",
    response_model=SafetyReviewOut,
    status_code=201,
    summary="Submit for a safety review",
    description="Assigned coordinator only (SPM-120), while the event is in planning, with both notes at once; "
    "Venue Staff and technical support usually send their parts through `/safety-handoff`. Refused with 409, "
    "naming what is `missing`, until a venue booking is confirmed and every requested equipment line is "
    "reserved (an event needing no equipment has nothing to wait for). Copies the venue, equipment, and "
    "event facts into the review with the crowd-movement and placement notes, moves the event to "
    "`safety review`, and notifies every Safety Officer. 503 when the arrangements cannot be checked.",
    responses=error_responses(403, 404, 409, 503),
)
def submit_safety_review(
    body: SafetySubmission,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.submit_safety_review(event_id, body, caller["userId"], authorization)


@router.get(
    "/{event_id}/safety-handoff",
    response_model=SafetyHandoffOut,
    summary="Arrangements sent to the Safety Officer",
    description="SPM-120, change 6. Which arrangements Venue Staff and technical support have sent this round, and "
    "whether the event needs technical ones. Organisers see it for their own organisation's events, staff for any "
    "event; attendees get 403. 503 when the arrangements cannot be checked.",
    responses=error_responses(403, 404, 503),
)
def get_safety_handoff(
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return service.safety_handoff(event_id, caller, authorization)


@router.post(
    "/{event_id}/safety-handoff/venue",
    response_model=SafetyHandoffOut,
    summary="Send the venue arrangements to the Safety Officer",
    description="Venue Staff only (SPM-120, change 6), while the event is in planning. 409, naming what is "
    "`missing`, until every requested venue is approved for the event's date and time. The review opens for the "
    "Safety Officers once the technical arrangements are in too, or at once when the event has no equipment; "
    "`review` is then set and the coordinator is told.",
    responses=error_responses(403, 404, 409, 503),
)
def send_venue_arrangements(
    body: SafetyVenueHandoff,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.send_venue_arrangements(event_id, body, caller["userId"], authorization)


@router.post(
    "/{event_id}/safety-handoff/technical",
    response_model=SafetyHandoffOut,
    summary="Send the technical arrangements to the Safety Officer",
    description="Technical support only (SPM-120, change 6), while the event is in planning. 409 when the event "
    "has no equipment, or, naming what is `missing`, until every equipment line is reserved or recorded as not "
    "required. The review opens once the venue arrangements are in too; `review` is then set.",
    responses=error_responses(403, 404, 409, 503),
)
def send_technical_arrangements(
    body: SafetyTechnicalHandoff,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport"})
    return service.send_technical_arrangements(event_id, body, caller["userId"], authorization)


@router.get(
    "/{event_id}/safety-reviews",
    response_model=list[SafetyReviewOut],
    summary="Safety reviews of an event",
    description="SPM-120. Every review, newest first, with the facts submitted and the outcome. Organisers see "
    "them for their own organisation's events, staff for any event; attendees get 403.",
    responses=error_responses(403, 404),
)
def get_safety_reviews(
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return service.get_safety_reviews(event_id, caller)


@router.post(
    "/{event_id}/safety-reviews/{review_id}/approve",
    response_model=SafetyReviewOut,
    summary="Approve a safety review",
    description="Safety Officers only; every other role gets 403 (SPM-120 AC8). Records the decision, the "
    "officer, and the time, and moves the event to `safety approved`, ready for the coordinator to confirm "
    "(SPM-72). 409 unless the review is pending.",
    responses=error_responses(403, 404, 409),
)
def approve_safety_review(
    body: SafetyApproval,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    review_id: str = Path(..., description="Safety review id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"safety"})
    return service.approve_safety_review(event_id, review_id, body, caller["userId"], authorization)


@router.post(
    "/{event_id}/safety-reviews/{review_id}/reject",
    response_model=SafetyReviewOut,
    summary="Reject a safety review",
    description="Safety Officers only; every other role gets 403 (SPM-120 AC8). A reason is required. The "
    "event returns to `planning`, so it does not proceed to preparation, but it is not cancelled; the "
    "coordinator and organiser are notified and the coordinator can submit again.",
    responses=error_responses(403, 404, 409),
)
def reject_safety_review(
    body: SafetyRejection,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    review_id: str = Path(..., description="Safety review id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"safety"})
    return service.reject_safety_review(event_id, review_id, body, caller["userId"], authorization)


@router.post(
    "/{event_id}/safety-reviews/{review_id}/request-changes",
    response_model=SafetyReviewOut,
    summary="Request changes on a safety review",
    description="Safety Officers only; every other role gets 403 (SPM-120 AC8). Records what must change and "
    "returns the event to `planning`. Arrangements named in `affected` (`venue`, `technical`) are flagged "
    "for re-checking by venue staff or technical support. 503 if they cannot be flagged; nothing is saved then.",
    responses=error_responses(403, 404, 409, 503),
)
def request_safety_changes(
    body: SafetyChangeRequest,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    review_id: str = Path(..., description="Safety review id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"safety"})
    return service.request_safety_changes(event_id, review_id, body, caller["userId"], authorization)


@router.get(
    "/{event_id}/change-requests",
    response_model=list[ChangeRequestOut],
    summary="Change requests",
    description="SPM-106. Every change request on the event, newest first, with current and proposed values. "
    "Organisers see them for their own organisation's events, staff for any event; attendees get 403.",
    responses=error_responses(403, 404),
)
def list_change_requests(
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url)
    return service.list_change_requests(event_id, caller)


@router.post(
    "/{event_id}/change-requests",
    response_model=ChangeRequestOut,
    status_code=201,
    summary="Request a change",
    description="The event's organiser or a colleague in their organisation (SPM-106). States each field to "
    "change (see `/events/changeable-fields`) with its proposed value, and a reason (422 without one). "
    "Allowed while the event is under review, approved, in planning, or confirmed; 409 for a draft, a "
    "submitted request, a finished event, or when a request is already pending. The event is not changed; "
    "the assigned coordinator is emailed (best effort).",
    responses=error_responses(403, 404, 409),
)
def raise_change_request(
    body: ChangeRequestCreate,
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"organiser"})
    return service.raise_change_request(event_id, body, caller, authorization)


@router.post(
    "/{event_id}/change-requests/{change_request_id}/withdraw",
    response_model=ChangeRequestOut,
    summary="Withdraw a change request",
    description="The organiser who raised it, while it is pending (SPM-106 AC6). The coordinator is emailed.",
    responses=error_responses(403, 404, 409),
)
def withdraw_change_request(
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    change_request_id: str = Path(..., description="Change request id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"organiser"})
    return service.withdraw_change_request(event_id, change_request_id, caller, authorization)


@router.post(
    "/{event_id}/change-requests/{change_request_id}/accept",
    response_model=ChangeRequestOut,
    summary="Accept a change request",
    description="Assigned coordinator only (SPM-106 AC7). Applies the proposed values with the same rules as "
    "`PATCH /events/{id}`: a significant change on an event with confirmed arrangements, or on a confirmed "
    "event, is 409 naming what is affected until `confirmSignificantChange` is true. The organiser is "
    "notified with the optional reason.",
    responses=error_responses(403, 404, 409, 503),
)
def accept_change_request(
    body: ChangeRequestAccept,
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    change_request_id: str = Path(..., description="Change request id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.accept_change_request(event_id, change_request_id, body, caller["userId"], authorization)


@router.post(
    "/{event_id}/change-requests/{change_request_id}/decline",
    response_model=ChangeRequestOut,
    summary="Decline a change request",
    description="Assigned coordinator only (SPM-106 AC7). A reason is required; the organiser is notified "
    "with it. The event is unchanged.",
    responses=error_responses(403, 404, 409),
)
def decline_change_request(
    body: ChangeRequestDecline,
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    change_request_id: str = Path(..., description="Change request id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.decline_change_request(event_id, change_request_id, body, caller["userId"], authorization)


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


@router.post(
    "/{event_id}/approve",
    response_model=EventApprovalOut,
    summary="Approve a request",
    description="Assigned coordinator only (SPM-69). Moves an `under review` request to `planning` and "
    "records the decision, the decider, the time, and the optional `note`, which the organiser sees "
    "(`GET /events/{id}/decision`). The organiser is emailed (best effort). A `changes requested` request "
    "still has open clarifications, so it returns 409 with `requiresConfirmation` until "
    "`confirmOpenClarifications` is true. Approval does not book a venue or reserve equipment. 409 when no "
    "coordinator is assigned or the request is not under review; 403 for any other coordinator.",
    responses=error_responses(403, 404, 409),
)
def approve_event(
    body: EventApproval,
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.approve_event(
        event_id, caller["userId"], body.note, body.confirmOpenClarifications, authorization
    )


@router.post("/{event_id}/reject", response_model=EventOut)
def reject_event(
    event_id: str,
    body: EventDecision,
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.reject_event(event_id, caller["userId"], body.reason or "", authorization)


@router.get(
    "/{event_id}/confirmation",
    response_model=ConfirmationOut,
    summary="Can the event be confirmed?",
    description="Assigned coordinator only (SPM-72 AC2). `ready` is true when nothing is missing; otherwise "
    "`missing` names each gap: a venue not approved for the event's date and time, equipment neither reserved "
    "nor recorded as not required, the safety review (SPM-120), or the event's stage. 503 when the "
    "arrangements cannot be checked.",
    responses=error_responses(403, 404, 409, 503),
)
def get_confirmation(
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.confirmation(event_id, caller["userId"], authorization)


@router.post(
    "/{event_id}/confirm",
    response_model=EventConfirmOut,
    summary="Confirm an event",
    description="Assigned coordinator only (SPM-72). Only after the Safety Officer has approved it (SPM-120), and "
    "only while every requested venue booking is approved for the event's date and time and every equipment line "
    "is reserved or recorded as not required, checked again now. Moves the event to `confirmed`, records "
    "`decidedBy` and `decidedAt`, and notifies the organiser and the venue staff and technical support who "
    "handled the arrangements. A registration-enabled event is then listed for attendees once its period opens. "
    "409 with `missing` when anything is outstanding; 503 when the arrangements cannot be checked.",
    responses=error_responses(403, 404, 409, 503),
)
def confirm_event(
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.confirm_event(event_id, caller["userId"], authorization)


@router.post(
    "/{event_id}/equipment-lines/{equipment_id}/not-required",
    response_model=EventOut,
    summary="Record an equipment line as not required",
    description="Assigned coordinator only (SPM-72 AC1), while the event is in planning. A reason is required; "
    "the change is written to the activity log. A line recorded as not required no longer blocks the safety "
    "review or confirmation.",
    responses=error_responses(403, 404, 409),
)
def mark_equipment_not_required(
    body: EquipmentNotRequired,
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    equipment_id: str = Path(..., description="Equipment type id on the event's equipment lines, e.g. `eq1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.mark_equipment_not_required(event_id, equipment_id, body, caller["userId"], authorization)


@router.delete(
    "/{event_id}/equipment-lines/{equipment_id}/not-required",
    response_model=EventOut,
    summary="Record an equipment line as required again",
    description="Assigned coordinator only, while the event is in planning. Undoes `not-required`.",
    responses=error_responses(403, 404, 409),
)
def mark_equipment_required(
    event_id: str = Path(..., description="Event id, e.g. `e3`."),
    equipment_id: str = Path(..., description="Equipment type id on the event's equipment lines, e.g. `eq1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.mark_equipment_required(event_id, equipment_id, caller["userId"], authorization)


@router.post(
    "/{event_id}/complete",
    response_model=EventOut,
    summary="Mark completed",
    description="Assigned coordinator only (SPM-73). Only a confirmed event, and only once its "
    "proposedEndAt has passed. Records the change in the activity log. 409 if the event is not "
    "confirmed or has not yet ended; 403 if the caller is not the assigned coordinator.",
    responses=error_responses(403, 404, 409),
)
def complete_event(
    event_id: str = Path(..., description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EventService = Depends(get_event_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.complete_event(event_id, caller["userId"], authorization)


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
