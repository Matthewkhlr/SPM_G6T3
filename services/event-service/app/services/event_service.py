import logging
import time
from datetime import datetime, timedelta
from typing import NamedTuple
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_change_request_dao import EventChangeRequestDAO
from app.dao.event_dao import EventDAO
from app.dao.event_field_change_dao import EventFieldChangeDAO
from app.dao.event_review_dao import EventReviewDAO
from app.dao.event_safety_handoff_dao import EventSafetyHandoffDAO
from app.dao.event_safety_review_dao import EventSafetyReviewDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.models.event import Event
from app.models.event_assignment import EventAssignment
from app.models.event_change_request import EventChangeRequest
from app.models.event_clarification_reply import EventClarificationReply
from app.models.event_field_change import EventFieldChange
from app.models.event_review import EventReview
from app.models.event_safety_handoff import EventSafetyHandoff
from app.models.event_safety_review import EventSafetyReview
from app.models.event_status_history import EventStatusHistory
from app.core.config import settings
from app.orchestration.clients import (
    affected_arrangements,
    booked_venue_capacities,
    current_registration_count,
    equipment_names,
    event_bookings,
    equipment_requests_for,
    equipment_reservations_for,
    flag_arrangements,
    flag_technical_arrangements,
    flag_venue_arrangements,
    list_users,
    organisation_names,
    record_notification,
    release_event_holds,
    registered_attendees,
    registration_count,
    send_notification,
    venue_details,
)
from app.schemas.event import (
    CHANGEABLE_FIELDS,
    AffectedArrangement,
    ChangeableFieldsOut,
    ChangeRequestAccept,
    ChangeRequestCreate,
    ChangeRequestDecline,
    ChangeRequestOut,
    ClarificationCreate,
    ClarificationEntryOut,
    ClarificationOut,
    ClarificationReplyCreate,
    ConfirmationGap,
    ConfirmationOut,
    CoordinatorCandidateOut,
    EventActivityOut,
    EventApprovalOut,
    EventAssignmentCreate,
    EventAssignmentOut,
    EventCoordinatorOut,
    EventCreate,
    EventConfirmOut,
    EventDecisionOut,
    EquipmentNotRequired,
    EventDraftUpsert,
    EventInternalNotesOut,
    EventOut,
    OrganiserDraftPatch,
    RequirementOptionsOut,
    EventUpdate,
    EventUpdateOut,
    RegistrationAccessOut,
    RegistrationSettingsOut,
    RegistrationSettingsUpdate,
    SafetyApproval,
    SafetyChangeRequest,
    SafetyEquipmentLine,
    SafetyHandoffOut,
    SafetyHandoffPart,
    SafetyPackage,
    SafetyRejection,
    SafetyReviewOut,
    SafetySubmission,
    SafetyTechnicalHandoff,
    SafetyVenueFacts,
    SafetyVenueHandoff,
    SignificantFieldsOut,
)
from app.services.arrangements import (
    SETTLED_REQUESTS,
    equipment_gaps,
    requested_lines,
    technical_needed,
    venue_gaps,
)
from shared.exceptions.http import conflict, forbidden, not_found
from shared.services.base import BaseService

logger = logging.getLogger("perf.event_service")

# Full intended event lifecycle. The status column is a free VARCHAR(32) with
# no DB-level enum, so this is documentation for future transitions, not an
# enforced constraint. Approval moves a request straight to "planning" (SPM-69).
EVENT_STATUSES = (
    "draft",
    "discarded",
    "submitted",
    "under review",
    "changes requested",
    "approved",
    "rejected",
    "planning",
    "safety review",
    "safety approved",
    "preparing",
    "prepared",
    "confirmed",
    "reconsidering",
    "completed",
    "cancelled",
)

# Statuses the coordinator review queue (GET /events/queue) includes.
QUEUE_STATUSES = ("submitted", "under review", "changes requested")
# Reject applies while the request waits for a decision. Assigning a
# coordinator moves a submitted request to "under review" (SPM-66 AC6), and it
# must still be decidable from there.
DECIDABLE_STATUSES = ("submitted", "under review")
# An assigned request under review, or waiting on the organiser. Its assigned
# coordinator can raise clarifications on it (SPM-68) or approve it (SPM-69).
IN_REVIEW_STATUSES = ("under review", "changes requested")
# SPM-68 AC2/AC5: raising a clarification moves a request to this status, and
# resolving the last open one returns it to "under review".
AWAITING_CLARIFICATION = "changes requested"
# event_reviews.action and .status for a clarification (SPM-68).
CLARIFICATION = "request_clarification"
OPEN = "open"
RESOLVED = "resolved"
# event_reviews.action -> the outcome shown to the organiser (SPM-69 AC3).
DECISIONS = {"approve": "approved", "reject": "rejected"}
# Staff who can see an event's coordinator; organisers see it only for their
# own organisation's events, and attendees not at all (SPM-59 AC5).
STAFF_ROLES = ("coordinator", "venue", "techsupport", "safety")

# SPM-80: published lists the organiser picks from. "No preference" is a real choice.
LAYOUT_OPTIONS = ["Theatre", "Boardroom", "Classroom", "Banquet", "U-shape", "No preference"]
FACILITY_OPTIONS = ["Projector", "PA system", "Video-conferencing", "Stage"]
ACCESSIBILITY_OPTIONS = ["Wheelchair accessible", "Hearing loop", "Accessible restrooms nearby"]

# SPM-71 AC1: these save without any warning.
QUIET_FIELDS = ("eventName", "description", "purpose", "category", "internalNotes", "organiserContact")
# SPM-71 AC2: editing any of these can invalidate a venue booking or an
# equipment reservation. "Required layout" is layoutPreference.
SIGNIFICANT_FIELDS = (
    "proposedStartAt",
    "proposedEndAt",
    "expectedAttendance",
    "layoutPreference",
    "accessibilityNeeds",
    "equipmentRequirements",
)
FIELD_LABELS = {
    "eventName": "Name",
    "description": "Description",
    "purpose": "Purpose",
    "category": "Category",
    "internalNotes": "Internal notes",
    "organiserContact": "Organiser contact",
    "proposedStartAt": "Start",
    "proposedEndAt": "End",
    "expectedAttendance": "Expected attendance",
    "layoutPreference": "Layout",
    "accessibilityNeeds": "Accessibility needs",
    "equipmentRequirements": "Equipment requirements",
    # SPM-68: a clarification can name any field of the request.
    "venueRequirements": "Venue requirements",
    "registrationEnabled": "Registration",
    "registrationOpensAt": "Registration opens",
    "registrationClosesAt": "Registration closes",
    "capacity": "Capacity",
}
# Finished events, and drafts that are not yet requests. They cannot be edited
# (SPM-71 AC7) or assigned a coordinator, and do not count toward a
# coordinator's active events (SPM-66 AC2). A draft still belongs to its
# organiser, who edits it through the draft endpoints.
LOCKED_STATUSES = ("completed", "cancelled", "rejected", "draft", "discarded")
# SPM-71 AC6: a confirmed event whose significant details changed no longer
# reads as fully confirmed while its arrangements are re-checked.
RECONSIDERING = "reconsidering"
# SPM-90 AC1: registration is set up from planning until the event is
# confirmed. "approved" is planning's older name, and a reconsidering event is
# still confirmed while its arrangements are re-checked.
# SPM-120: once the venue and equipment are confirmed, the coordinator sends a
# planning event for a safety review. Approval leaves it waiting for the
# coordinator to confirm it (SPM-72), after which preparation can begin;
# rejection or a change request returns it to planning, never cancelled.
SAFETY_REVIEW = "safety review"
SAFETY_APPROVED = "safety approved"
# A significant change in either sends the event back to planning for a new review.
SAFETY_STAGES = (SAFETY_REVIEW, SAFETY_APPROVED)
SAFETY_SUBMITTABLE_STATUSES = ("approved", "planning")
REGISTRATION_SETUP_STATUSES = (
    "approved", "planning", SAFETY_REVIEW, SAFETY_APPROVED, "preparing", "prepared", "confirmed", RECONSIDERING
)
# SPM-106 AC1: Under Review, Approved, Planning, or Confirmed, as the organiser
# sees them. Waiting on clarifications is still under review; preparing and
# prepared are planning; reconsidering is still confirmed. A submitted request
# has no coordinator to tell yet, a draft is edited directly (AC8), and a
# finished event takes no changes (AC9).
CHANGE_REQUEST_STATUSES = (
    "under review",
    AWAITING_CLARIFICATION,
    "approved",
    "planning",
    SAFETY_REVIEW,
    SAFETY_APPROVED,
    "preparing",
    "prepared",
    "confirmed",
    RECONSIDERING,
)
PENDING = "pending"
# Which arrangements a change can unsettle, so the coordinator sees it at a glance.
AFFECTS_VENUE = ("proposedStartAt", "proposedEndAt", "expectedAttendance", "layoutPreference", "accessibilityNeeds")
AFFECTS_EQUIPMENT = ("proposedStartAt", "proposedEndAt", "equipmentRequirements")
AFFECTS_REGISTRATION = ("proposedStartAt", "proposedEndAt", "expectedAttendance")


def _as_text(value) -> str | None:
    """Activity-log values are stored as text; datetimes use ISO 8601."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_value(value):
    """A field's value as change requests store it (JSON): datetimes in ISO 8601."""
    return value.isoformat() if isinstance(value, datetime) else value


def _field_list(changes: dict | None) -> str:
    return ", ".join(FIELD_LABELS.get(field, field).lower() for field in changes or {})


def _name_of(users: dict[str, dict], user_id: str) -> str:
    return users.get(user_id, {}).get("userName") or "The organiser"


def _change_request_out(row: EventChangeRequest, flagged: list[dict] = ()) -> ChangeRequestOut:
    return ChangeRequestOut(
        changeRequestId=row.changeRequestId,
        eventId=row.eventId,
        status=row.status,
        reason=row.summary or "",
        proposedChanges=row.proposedChanges or {},
        currentValues=row.currentValues,
        requestedBy=row.requestedBy,
        createdAt=row.createdAt,
        affectsVenue=bool(row.affectsVenue),
        affectsEquipment=bool(row.affectsEquipment),
        affectsRegistration=bool(row.affectsRegistration),
        reviewedBy=row.reviewedBy,
        reviewedAt=row.reviewedAt,
        decisionReason=row.decisionReason,
        flaggedArrangements=[AffectedArrangement(**arrangement) for arrangement in flagged],
    )


class Arrangements(NamedTuple):
    """An event's venue and equipment arrangements as just read, with what is missing."""

    gaps: list[dict]
    bookings: list[dict]
    requests: list[dict]
    reservations: list[dict]
    names: dict[str, str]


def _set_part(handoff: EventSafetyHandoff, kind: str, note: str | None, sender: str | None, at: datetime | None) -> None:
    """Record, or clear with Nones, the venue or technical part of a hand-off."""
    if kind == "venue":
        handoff.crowdMovement, handoff.venueSentBy, handoff.venueSentAt = note, sender, at
    else:
        handoff.equipmentPlacement, handoff.technicalSentBy, handoff.technicalSentAt = note, sender, at


def _handoff_out(event_id: str, handoff: EventSafetyHandoff | None, needed: bool) -> SafetyHandoffOut:
    venue = technical = None
    if handoff is not None and handoff.venueSentAt:
        venue = SafetyHandoffPart(sentBy=handoff.venueSentBy, sentAt=handoff.venueSentAt, note=handoff.crowdMovement)
    if handoff is not None and handoff.technicalSentAt:
        technical = SafetyHandoffPart(
            sentBy=handoff.technicalSentBy, sentAt=handoff.technicalSentAt, note=handoff.equipmentPlacement
        )
    return SafetyHandoffOut(eventId=event_id, venue=venue, technical=technical, technicalNeeded=needed)


def _missing(gaps: list[dict]) -> HTTPException:
    """409 naming everything missing: each gap, and the kinds for a quick check."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": " ".join(gap["message"] for gap in gaps),
            "missing": list(dict.fromkeys(gap["kind"] for gap in gaps)),
            "gaps": gaps,
        },
    )


def _safety_review_out(row: EventSafetyReview, flagged: list[dict] = ()) -> SafetyReviewOut:
    return SafetyReviewOut(
        reviewId=row.reviewId,
        eventId=row.eventId,
        status=row.status,
        submittedBy=row.submittedBy,
        submittedAt=row.submittedAt,
        package=SafetyPackage(**row.package),
        decidedBy=row.decidedBy,
        decidedAt=row.decidedAt,
        decisionNote=row.decisionNote,
        affected=list(row.affected or []),
        flaggedArrangements=[AffectedArrangement(**arrangement) for arrangement in flagged],
    )


def _setting_text(value) -> str:
    """A registration setting as the organiser reads it (SPM-90 AC6)."""
    if isinstance(value, bool):
        return "needed" if value else "not needed"
    if value is None:
        return "not set"
    if isinstance(value, datetime):
        return f"{value:%d %b %Y, %H:%M}"
    return str(value)


def _differs(old, new) -> bool:
    """None and an empty string both mean "not set", so moving between them is not an edit."""
    return (old if old != "" else None) != (new if new != "" else None)


def _is_registration_viewer(event: Event, caller: dict) -> bool:
    user_id = caller.get("userId")
    if not user_id:
        return False
    if caller.get("role") == "organiser" and user_id == event.organiserId:
        return True
    if caller.get("role") == "coordinator" and event.coordinatorId and user_id == event.coordinatorId:
        return True
    return False


def _is_event_organiser(event: Event, caller: dict) -> bool:
    """The organiser who filed the event, or a colleague in their organisation."""
    own = caller.get("userId") == event.organiserId
    same_org = bool(caller.get("organisationId")) and caller.get("organisationId") == event.organisationId
    return caller.get("role") == "organiser" and (own or same_org)


def _require_organiser_or_staff(event: Event, caller: dict, subject: str) -> None:
    """Organisers see `subject` only for their own organisation's events, staff
    for any event, and attendees never (SPM-66 AC5, SPM-68 AC6, SPM-69 AC3)."""
    role = caller.get("role")
    if role == "organiser":
        if not _is_event_organiser(event, caller):
            raise forbidden(f"You can only see the {subject} for your organisation's events")
    elif role not in STAFF_ROLES:
        raise forbidden(f"You do not have permission to see this event's {subject}")


def _require_assigned_coordinator(event: Event, coordinator_id: str, action: str) -> None:
    """With no coordinator there is no one to act yet (409); any other coordinator is refused (403)."""
    if not event.coordinatorId:
        raise conflict(f"This request has no coordinator yet. Assign one before you {action}.")
    if event.coordinatorId != coordinator_id:
        raise forbidden(f"Only the event's assigned coordinator can {action}")


def _has_open_clarifications(event: Event) -> bool:
    return any(review.action == CLARIFICATION and review.status == OPEN for review in event.reviews)


def _equipment_line_dicts(lines) -> list[dict]:
    """One line per equipment type. A repeat of the same type replaces the earlier line."""
    ordered: list[str] = []
    by_id: dict[str, dict] = {}
    for line in lines or []:
        data = line.model_dump() if hasattr(line, "model_dump") else dict(line)
        equipment_id = data["equipmentId"]
        if equipment_id not in by_id:
            ordered.append(equipment_id)
        by_id[equipment_id] = {
            "equipmentId": equipment_id,
            "quantity": data["quantity"],
            "technicalNotes": data.get("technicalNotes") or "",
        }
    return [by_id[equipment_id] for equipment_id in ordered]


def _accessibility_pair(value) -> tuple[str, list]:
    if isinstance(value, list):
        chosen = [str(item) for item in value if str(item).strip()]
        return ", ".join(chosen), chosen
    text = (value or "").strip()
    return text, [text] if text else []


def _write_requirements(event: Event, data, only_sent: bool) -> None:
    sent = data.model_fields_set

    def include(name: str) -> bool:
        return name in sent if only_sent else True

    if include("layoutPreference"):
        event.layoutPreference = data.layoutPreference
    if include("preferredLocation"):
        event.preferredLocation = data.preferredLocation or ""
    if include("requiredFacilities"):
        event.requiredFacilities = list(data.requiredFacilities or [])
    if include("accessibilityNote"):
        event.accessibilityNote = data.accessibilityNote or ""
    if include("accessibilityNeeds"):
        text, chosen = _accessibility_pair(data.accessibilityNeeds)
        event.accessibilityNeeds = text
        event.accessibilitySelections = chosen
    if include("equipmentLines"):
        event.equipmentLines = _equipment_line_dicts(data.equipmentLines)


def _date_near(proposed_start: datetime | None) -> bool:
    """True when the proposed start is within the configured lead, inclusive.

    ``timedelta.days`` drops the leftover hours, so a start 14 days and 23
    hours away would still look like 14 days. Compare the full span instead:
    the instant exactly ``event_proposed_date_near_days`` ahead is near, and
    one second later is not. A start already in the past is near.
    """
    if proposed_start is None:
        return False
    return proposed_start - datetime.utcnow() <= timedelta(days=settings.event_proposed_date_near_days)


def _to_out(
    row: Event,
    authorization: str | None = None,
    org_names: dict[str, str] | None = None,
    out_type: type[EventOut] = EventOut,
    **extra,
) -> EventOut:
    if org_names is None:
        org_names = organisation_names(authorization)
    return out_type(
        **extra,
        eventId=row.eventId,
        eventName=row.eventName,
        status=row.status,
        purpose=row.purpose,
        description=row.description,
        category=row.category,
        proposedStartAt=row.proposedStartAt,
        proposedEndAt=row.proposedEndAt,
        expectedAttendance=row.expectedAttendance,
        venueRequirements=row.venueRequirements,
        accessibilityNeeds=row.accessibilityNeeds or "",
        equipmentRequirements=row.equipmentRequirements,
        layoutPreference=row.layoutPreference,
        preferredLocation=row.preferredLocation or "",
        requiredFacilities=list(row.requiredFacilities or []),
        accessibilityNote=row.accessibilityNote or "",
        accessibilitySelections=list(row.accessibilitySelections or []),
        equipmentLines=list(row.equipmentLines or []),
        registrationEnabled=row.registrationEnabled,
        registrationOpensAt=row.registrationOpensAt,
        registrationClosesAt=row.registrationClosesAt,
        capacity=row.capacity,
        submittedAt=row.submittedAt,
        organisationId=row.organisationId,
        organisationName=org_names.get(row.organisationId) if row.organisationId else None,
        coordinatorId=row.coordinatorId,
        organiserContact=row.organiserContact or "",
        dateNear=_date_near(row.proposedStartAt),
        registeredCount=registration_count(row.eventId, authorization),
        confirmedBy=row.confirmedBy,
        confirmedAt=row.confirmedAt,
        hasOpenClarifications=_has_open_clarifications(row),
    )


def _to_out_list(
    rows: list[Event], authorization: str | None, label: str
) -> list[EventOut]:
    """_to_out() over a list, with timing so the registration-count fan-out
    cost is visible separately from the DB query that produced `rows`.

    organisation_names() is fetched ONCE here and passed to every _to_out()
    call, rather than letting each one fetch it - same reasoning as the
    registration_count() fix: one network call per list, not one per row.
    """
    org_names = organisation_names(authorization)
    start = time.perf_counter()
    result = [_to_out(row, authorization, org_names) for row in rows]
    logger.info(
        "%s _to_out (incl. registration_count) took %.3fs total for %d rows",
        label,
        time.perf_counter() - start,
        len(rows),
    )
    return result


class EventService(BaseService):
    """Business logic for event requests: drafts, submission, coordinator
    decisions, and coordinator assignment. Reads and writes go through the
    injected DAOs; this class owns the transaction boundary (commit/refresh)
    since a use case can span multiple DAOs sharing the same session (e.g.
    deciding an event writes both the Event row and an EventStatusHistory
    row as one commit)."""

    def __init__(
        self,
        db: Session,
        event_dao: EventDAO,
        assignment_dao: EventAssignmentDAO,
        history_dao: EventStatusHistoryDAO,
        field_change_dao: EventFieldChangeDAO | None = None,
        review_dao: EventReviewDAO | None = None,
        change_request_dao: EventChangeRequestDAO | None = None,
        safety_dao: EventSafetyReviewDAO | None = None,
        handoff_dao: EventSafetyHandoffDAO | None = None,
    ):
        super().__init__(db)
        self.event_dao = event_dao
        self.assignment_dao = assignment_dao
        self.history_dao = history_dao
        self.field_change_dao = field_change_dao or EventFieldChangeDAO(db)
        self.review_dao = review_dao or EventReviewDAO(db)
        self.change_request_dao = change_request_dao or EventChangeRequestDAO(db)
        self.safety_dao = safety_dao or EventSafetyReviewDAO(db)
        self.handoff_dao = handoff_dao or EventSafetyHandoffDAO(db)

    def _require_event(self, event_id: str) -> Event:
        return self._require(self.event_dao.get_by_id(event_id), "Event not found")

    def list_events(self, authorization: str | None = None) -> list[EventOut]:
        """Every event except drafts — a draft is only visible to its own organiser."""
        query_start = time.perf_counter()
        rows = self.event_dao.list_excluding_draft()
        logger.info(
            "list_events DB query took %.3fs, %d rows",
            time.perf_counter() - query_start,
            len(rows),
        )
        return _to_out_list(rows, authorization, "list_events")

    def list_all_events(self, authorization: str | None = None) -> list[EventOut]:
        """Every event except rejected ones, drafts, and discarded drafts."""
        query_start = time.perf_counter()
        rows = self.event_dao.list_excluding_statuses(["rejected", "draft", "discarded"])
        logger.info(
            "list_all_events DB query took %.3fs, %d rows",
            time.perf_counter() - query_start,
            len(rows),
        )
        return _to_out_list(rows, authorization, "list_all_events")

    def list_confirmed_events(self, authorization: str | None = None) -> list[EventOut]:
        """Only events that have been confirmed (SPM-72 confirm_event sets the status)."""
        query_start = time.perf_counter()
        rows = self.event_dao.list_by_status("confirmed")
        logger.info(
            "list_confirmed_events DB query took %.3fs, %d rows",
            time.perf_counter() - query_start,
            len(rows),
        )
        return _to_out_list(rows, authorization, "list_confirmed_events")

    def list_upcoming_events(self, authorization: str | None = None) -> list[EventOut]:
        now = datetime.utcnow()
        statuses = ["rejected", "cancelled", "completed", "draft", "discarded"]
        query_start = time.perf_counter()
        rows = self.event_dao.list_upcoming_excluding_statuses(now, statuses)
        logger.info(
            "list_upcoming_events DB query took %.3fs, %d rows",
            time.perf_counter() - query_start,
            len(rows),
        )
        return _to_out_list(rows, authorization, "list_upcoming_events")

    def get_event(self, event_id: str, authorization: str | None = None) -> EventOut:
        return _to_out(self._require_event(event_id), authorization)

    def registration_access(self, event_id: str, caller: dict) -> RegistrationAccessOut:
        """Facts the registration list is allowed to show.

        Only the event's organiser and its assigned coordinator may read this.
        A disabled registration window is refused so no list is offered.
        """
        event = self._require_event(event_id)
        if not _is_registration_viewer(event, caller):
            raise forbidden("You do not have permission to view these registrations.")
        if not event.registrationEnabled:
            raise not_found("Registration has not been enabled for this event.")
        return RegistrationAccessOut(
            eventId=event.eventId,
            registrationEnabled=True,
            registrationOpensAt=event.registrationOpensAt,
            registrationClosesAt=event.registrationClosesAt,
            capacity=event.capacity,
        )

    def list_submission_queue(
        self,
        authorization: str | None = None,
        sort: str | None = None,
        assigned_to: str | None = None,
    ) -> list[EventOut]:
        """Coordinator review queue: submitted / under review / changes
        requested events - excludes drafts and everything else.

        Role-gating happens in the router (resolve_caller, allowed_roles=
        {"coordinator"}) before this is called - same pattern as
        approve_event/reject_event.

        sort="proposedStartAt" orders by the proposed event date instead of
        the default (submittedAt ascending - longest-waiting first).
        assigned_to filters to one coordinator's own assignments.
        """
        query_start = time.perf_counter()
        if sort == "proposedStartAt":
            rows = self.event_dao.list_by_statuses_ordered_by_proposed_start(list(QUEUE_STATUSES))
        else:
            rows = self.event_dao.list_by_statuses_ordered_by_submitted(list(QUEUE_STATUSES))
        if assigned_to is not None:
            rows = [row for row in rows if row.coordinatorId == assigned_to]
        logger.info(
            "list_submission_queue DB query took %.3fs, %d rows",
            time.perf_counter() - query_start,
            len(rows),
        )
        return _to_out_list(rows, authorization, "list_submission_queue")

    def create_event(
        self,
        data: EventCreate,
        organiser_id: str,
        organisation_id: str | None,
        authorization: str | None = None,
    ) -> EventOut:
        """Create and immediately submit an event request.

        For saving an incomplete request instead, see create_draft().
        """
        now = datetime.utcnow()
        row = Event(
            eventId=str(uuid4()),
            organiserId=organiser_id,
            organisationId=organisation_id,
            coordinatorId=None,
            eventName=data.eventName,
            purpose=data.purpose,
            description=data.description,
            category=data.category,
            proposedStartAt=data.proposedStartAt,
            proposedEndAt=data.proposedEndAt,
            expectedAttendance=data.expectedAttendance,
            venueRequirements=data.venueRequirements,
            accessibilityNeeds=data.accessibilityNeeds,
            equipmentRequirements=data.equipmentRequirements,
            layoutPreference=data.layoutPreference,
            registrationEnabled=data.registrationEnabled,
            registrationOpensAt=data.registrationOpensAt,
            registrationClosesAt=data.registrationClosesAt,
            capacity=data.capacity,
            status="submitted",
            submittedAt=now,
            createdAt=now,
            updatedAt=now,
        )
        self.event_dao.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_out(row, authorization)

    def create_draft(
        self,
        data: EventDraftUpsert,
        organiser_id: str,
        organisation_id: str | None,
        authorization: str | None = None,
    ) -> EventOut:
        now = datetime.utcnow()
        row = Event(
            eventId=str(uuid4()),
            organiserId=organiser_id,
            organisationId=organisation_id,
            coordinatorId=None,
            eventName=data.eventName,
            purpose=data.purpose,
            description=data.description,
            category=data.category,
            proposedStartAt=data.proposedStartAt,
            proposedEndAt=data.proposedEndAt,
            expectedAttendance=data.expectedAttendance or 0,
            venueRequirements=data.venueRequirements,
            accessibilityNeeds="",
            equipmentRequirements=data.equipmentRequirements,
            layoutPreference=data.layoutPreference,
            registrationEnabled=False,
            registrationOpensAt=None,
            registrationClosesAt=None,
            capacity=0,
            status="draft",
            submittedAt=None,
            createdAt=now,
            updatedAt=now,
        )
        _write_requirements(row, data, only_sent=False)
        self.event_dao.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_out(row, authorization)

    def _get_own_draft(self, event_id: str, organiser_id: str) -> Event:
        event = self._require_event(event_id)
        if event.organiserId != organiser_id:
            raise forbidden("You do not have permission to edit this event")
        if event.status != "draft":
            raise conflict(f"Event is already {event.status}")
        return event

    def update_draft(
        self,
        event_id: str,
        data: EventDraftUpsert,
        organiser_id: str,
        authorization: str | None = None,
    ) -> EventOut:
        event = self._get_own_draft(event_id, organiser_id)
        event.eventName = data.eventName
        event.purpose = data.purpose
        event.description = data.description
        event.category = data.category
        event.proposedStartAt = data.proposedStartAt
        event.proposedEndAt = data.proposedEndAt
        event.expectedAttendance = data.expectedAttendance or 0
        event.venueRequirements = data.venueRequirements
        event.equipmentRequirements = data.equipmentRequirements
        _write_requirements(event, data, only_sent=True)
        event.updatedAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(event)
        return _to_out(event, authorization)

    def requirement_options(self) -> RequirementOptionsOut:
        return RequirementOptionsOut(
            layouts=list(LAYOUT_OPTIONS),
            facilities=list(FACILITY_OPTIONS),
            accessibility=list(ACCESSIBILITY_OPTIONS),
        )

    def patch_own_draft(
        self,
        event_id: str,
        data: OrganiserDraftPatch,
        organiser_id: str,
        authorization: str | None = None,
    ) -> EventOut:
        """SPM-80: the owning organiser records structured requirements on a draft."""
        event = self._get_own_draft(event_id, organiser_id)
        sent = data.model_fields_set
        for field in (
            "eventName",
            "purpose",
            "description",
            "category",
            "proposedStartAt",
            "proposedEndAt",
            "venueRequirements",
            "equipmentRequirements",
        ):
            if field in sent:
                setattr(event, field, getattr(data, field))
        if "expectedAttendance" in sent and data.expectedAttendance is not None:
            event.expectedAttendance = data.expectedAttendance
        _write_requirements(event, data, only_sent=True)
        event.updatedAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(event)
        return _to_out(event, authorization)

    def submit_stored_draft(
        self, event_id: str, organiser_id: str, authorization: str | None = None
    ) -> EventOut:
        """Submit a draft from the fields already saved on it."""
        event = self._get_own_draft(event_id, organiser_id)
        missing = []
        if not event.eventName:
            missing.append("eventName")
        if event.proposedStartAt is None:
            missing.append("proposedStartAt")
        if event.proposedEndAt is None:
            missing.append("proposedEndAt")
        if not event.expectedAttendance or event.expectedAttendance < 1:
            missing.append("expectedAttendance")
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing {', '.join(missing)}",
            )
        if event.proposedEndAt <= event.proposedStartAt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="proposedEndAt must be after proposedStartAt",
            )
        now = datetime.utcnow()
        self._record_status_change(event, "submitted", organiser_id)
        event.status = "submitted"
        event.submittedAt = now
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(event)
        return _to_out(event, authorization)

    def submit_draft(
        self,
        event_id: str,
        data: EventCreate,
        organiser_id: str,
        authorization: str | None = None,
    ) -> EventOut:
        event = self._get_own_draft(event_id, organiser_id)
        now = datetime.utcnow()
        event.eventName = data.eventName
        event.purpose = data.purpose
        event.description = data.description
        event.category = data.category
        event.proposedStartAt = data.proposedStartAt
        event.proposedEndAt = data.proposedEndAt
        event.expectedAttendance = data.expectedAttendance
        event.venueRequirements = data.venueRequirements
        event.accessibilityNeeds = data.accessibilityNeeds
        event.equipmentRequirements = data.equipmentRequirements
        event.layoutPreference = data.layoutPreference
        event.registrationEnabled = data.registrationEnabled
        event.registrationOpensAt = data.registrationOpensAt
        event.registrationClosesAt = data.registrationClosesAt
        event.capacity = data.capacity
        self._record_status_change(event, "submitted", organiser_id)
        event.status = "submitted"
        event.submittedAt = now
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(event)
        return _to_out(event, authorization)

    def list_my_drafts(self, organiser_id: str, authorization: str | None = None) -> list[EventOut]:
        rows = self.event_dao.list_drafts_by_organiser(organiser_id)
        return _to_out_list(rows, authorization, "list_my_drafts")

    def list_my_events(self, organiser_id: str, authorization: str | None = None) -> list[EventOut]:
        """Every event the caller organises, at any stage, other than one they discarded.
        SPM-121: each carries its latest safety review status, so the organiser can
        see an event waiting on the review or sent back for safety changes."""
        rows = self.event_dao.list_by_organiser_excluding_statuses(organiser_id, ["discarded"])
        events = _to_out_list(rows, authorization, "list_my_events")
        latest = self.safety_dao.latest_status_by_event([row.eventId for row in rows])
        for event in events:
            event.safetyReviewStatus = latest.get(event.eventId)
        return events

    def discard_draft(
        self, event_id: str, organiser_id: str, authorization: str | None = None
    ) -> EventOut:
        """Discard an event request while it is still a draft.

        Only the owning organiser can discard, and only while the event has
        never been submitted - once it's in the review pipeline it can only
        move forward (approved/rejected), not disappear.
        """
        event = self._require_event(event_id)
        if event.organiserId != organiser_id:
            raise forbidden("You do not have permission to discard this event")
        if event.status != "draft":
            raise forbidden(f"Only a draft can be discarded (event is {event.status})")
        self._record_status_change(event, "discarded", organiser_id)
        event.status = "discarded"
        event.updatedAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(event)
        return _to_out(event, authorization)

    def get_activity_log(
        self, event_id: str, authorization: str | None = None
    ) -> list[EventActivityOut]:
        """Status changes, field edits, and coordinator assignments, oldest
        first. An edit or assignment and the status change it caused share a
        timestamp, so the cause is listed first."""
        self._require_event(event_id)
        assignments = []
        previous = None
        for row in self.assignment_dao.list_by_event(event_id):
            assignments.append(
                EventActivityOut(
                    historyId=row.assignmentId,
                    eventId=row.eventId,
                    kind="assignment",
                    field="coordinatorId",
                    oldValue=previous,
                    newValue=row.coordinatorId,
                    changedBy=row.assignedBy,
                    createdAt=row.assignedAt,
                )
            )
            previous = row.coordinatorId
        edits = [
            EventActivityOut(
                historyId=row.changeId,
                eventId=row.eventId,
                kind="edit",
                field=row.field,
                oldValue=row.oldValue,
                newValue=row.newValue,
                changedBy=row.changedBy,
                createdAt=row.createdAt,
            )
            for row in self.field_change_dao.list_by_event(event_id)
        ]
        changes = [
            EventActivityOut(
                historyId=row.historyId,
                eventId=row.eventId,
                kind="status",
                fromStatus=row.fromStatus,
                toStatus=row.toStatus,
                changedBy=row.changedBy,
                note=row.note,
                createdAt=row.createdAt,
            )
            for row in self.history_dao.list_by_event(event_id)
        ]
        return sorted(assignments + edits + changes, key=lambda entry: (entry.createdAt, entry.kind == "status"))

    @staticmethod
    def significant_fields() -> SignificantFieldsOut:
        return SignificantFieldsOut(fields=list(SIGNIFICANT_FIELDS), quietFields=list(QUIET_FIELDS))

    def get_internal_notes(self, event_id: str) -> EventInternalNotesOut:
        event = self._require_event(event_id)
        return EventInternalNotesOut(eventId=event.eventId, internalNotes=event.internalNotes or "")

    def update_event(
        self,
        event_id: str,
        data: EventUpdate,
        coordinator_id: str,
        authorization: str | None = None,
    ) -> EventUpdateOut:
        """SPM-71: the assigned coordinator edits an event during planning.

        Quiet fields save straight away (AC1). When a significant field (AC2)
        changes on an event holding a confirmed venue booking or equipment
        reservation, nothing is saved until the coordinator confirms, and the
        409 names each affected arrangement (AC3). A confirmed save marks those
        arrangements for re-verification (AC4) and a confirmed event becomes
        `reconsidering` (AC6). Every changed field is logged (AC5). Finished
        events cannot be edited (AC7).
        """
        event = self._require_event(event_id)
        if event.coordinatorId != coordinator_id:
            raise forbidden("Only the event's assigned coordinator can edit it")
        flagged = self._apply_changes(event, data, coordinator_id, authorization)
        self.db.commit()
        self.db.refresh(event)
        return _to_out(
            event,
            authorization,
            out_type=EventUpdateOut,
            internalNotes=event.internalNotes or "",
            flaggedArrangements=[AffectedArrangement(**row) for row in flagged],
        )

    def _apply_changes(
        self, event: Event, data: EventUpdate, changed_by: str, authorization: str | None
    ) -> list[dict]:
        """SPM-71's edit rules, shared by a coordinator's edit and an accepted
        change request (SPM-106). Returns the arrangements flagged for
        re-verification. The caller commits."""
        if event.status in LOCKED_STATUSES:
            raise conflict(f"This event is {event.status}, so it can no longer be edited")
        changes = {
            field: value
            for field, value in data.changed_values().items()
            if _differs(getattr(event, field), value)
        }
        start = changes.get("proposedStartAt", event.proposedStartAt)
        end = changes.get("proposedEndAt", event.proposedEndAt)
        if start and end and end <= start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The end must be after the start",
            )
        if not changes:
            return []

        significant = [field for field in SIGNIFICANT_FIELDS if field in changes]
        flagged: list[dict] = []
        if significant:
            summary = self._change_summary(event, changes, significant)
            if data.confirmSignificantChange:
                # Flag before saving: if the save then failed, the arrangements
                # would be re-checked needlessly, which is safe; the reverse order
                # could leave a changed event with arrangements nobody re-checks.
                flagged = flag_arrangements(event.eventId, summary, authorization)
            else:
                affected = affected_arrangements(event.eventId, authorization)
                if affected or event.status in ("confirmed", *SAFETY_STAGES):
                    raise self._confirmation_required(event, significant, affected)

        now = datetime.utcnow()
        if significant and event.status == "confirmed":
            self._record_status_change(event, RECONSIDERING, changed_by, summary, now)
            event.status = RECONSIDERING
        elif significant and event.status in SAFETY_STAGES:
            self._supersede_safety_review(event, changed_by, summary, now)
        handoff = self.handoff_dao.get(event.eventId)
        if significant and handoff is not None:
            # SPM-120: arrangements sent before the change must be sent again.
            self.handoff_dao.delete(handoff)
        self._log_and_set(event, changes, changed_by, now)
        return flagged

    def _log_and_set(self, event: Event, changes: dict, changed_by: str, now: datetime) -> None:
        """Write each change to the activity log (SPM-71 AC5, SPM-90 AC7), then apply it."""
        for field, value in changes.items():
            self.field_change_dao.add(
                EventFieldChange(
                    changeId=str(uuid4()),
                    eventId=event.eventId,
                    field=field,
                    oldValue=_as_text(getattr(event, field)),
                    newValue=_as_text(value),
                    changedBy=changed_by,
                    createdAt=now,
                )
            )
            setattr(event, field, value)
        event.updatedAt = now

    @staticmethod
    def _change_summary(event: Event, changes: dict, fields: list[str]) -> str:
        parts = [
            f"{FIELD_LABELS[field]}: {_as_text(getattr(event, field)) or 'not set'} -> "
            f"{_as_text(changes[field]) or 'not set'}"
            for field in fields
        ]
        return "Significant change. " + "; ".join(parts)

    @staticmethod
    def _confirmation_required(event: Event, significant: list[str], affected: list[dict]) -> HTTPException:
        labels = ", ".join(FIELD_LABELS[field].lower() for field in significant)
        if affected:
            message = (
                f"Changing {labels} affects arrangements that are already in place. They will be marked "
                "for re-verification. Confirm to save the change."
            )
        elif event.status == SAFETY_REVIEW:
            message = (
                f"Changing {labels} withdraws the pending safety review, and the event goes back to planning. "
                "Confirm to save the change."
            )
        elif event.status == SAFETY_APPROVED:
            message = (
                f"Changing {labels} withdraws the safety approval, and the event goes back to planning for a new "
                "safety review. Confirm to save the change."
            )
        else:
            message = f"Changing {labels} means this event will no longer read as confirmed. Confirm to save the change."
        status_change = None
        if event.status == "confirmed":
            status_change = {"from": event.status, "to": RECONSIDERING}
        elif event.status in SAFETY_STAGES:
            status_change = {"from": event.status, "to": "planning"}
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": message,
                "requiresConfirmation": True,
                "significantFields": significant,
                "arrangements": affected,
                "statusChange": status_change,
            },
        )

    def update_registration_settings(
        self,
        event_id: str,
        data: RegistrationSettingsUpdate,
        coordinator_id: str,
        authorization: str | None = None,
    ) -> RegistrationSettingsOut:
        """SPM-90: the assigned coordinator sets whether registration is needed,
        its period, and its capacity, from planning until confirmed (AC1).

        Registration must close after it opens and no later than the event
        starts (AC2). A capacity below the number already registered is refused
        with that number (AC4). A capacity above what the booked venue holds in
        the event's layout (AC3), or turning registration off while people are
        registered (AC5), saves nothing until the coordinator confirms. The
        sent capacity is checked even when unchanged, since bookings and
        registrations move on their own. Every changed field is logged (AC7).
        After the save the organiser is notified of any change (AC6), and
        attendees are told registration was turned off (AC5), best effort.
        """
        event = self._require_event(event_id)
        _require_assigned_coordinator(event, coordinator_id, "change its registration settings")
        if event.status not in REGISTRATION_SETUP_STATUSES:
            raise conflict(
                f"Registration can be set up from planning until the event is confirmed (this one is {event.status})"
            )
        sent = data.changed_values()
        if "registrationOpensAt" in sent or "registrationClosesAt" in sent:
            self._check_registration_period(event, sent)

        capacity = sent.get("capacity")
        turning_off = sent.get("registrationEnabled") is False and event.registrationEnabled
        registered = (
            current_registration_count(event.eventId, authorization) if capacity is not None or turning_off else 0
        )
        if capacity is not None and capacity < registered:
            people = "person is" if registered == 1 else "people are"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": f"{registered} {people} already registered, so the capacity cannot go below {registered}.",
                    "registeredCount": registered,
                },
            )
        warnings = []
        if capacity is not None and not data.confirmOverVenueCapacity:
            warnings += self._venue_capacity_warnings(event, capacity, authorization)
        if turning_off and registered and not data.confirmRegistrationOff:
            attendees = "attendee is" if registered == 1 else "attendees are"
            warnings.append(
                {
                    "kind": "registrationOff",
                    "registeredCount": registered,
                    "message": f"{registered} {attendees} already registered. Turning registration off will notify them.",
                }
            )
        if warnings:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": " ".join(warning["message"] for warning in warnings),
                    "requiresConfirmation": True,
                    "warnings": warnings,
                },
            )
        # Read before the save, so nobody is turned off without being told.
        to_notify = registered_attendees(event.eventId, authorization) if turning_off and registered else []

        changes = {field: value for field, value in sent.items() if _differs(getattr(event, field), value)}
        if changes:
            self._log_and_set(event, changes, coordinator_id, datetime.utcnow())
        self.db.commit()
        self.db.refresh(event)
        if changes:
            self._notify_registration_change(event, changes, to_notify, authorization)
        return _to_out(event, authorization, out_type=RegistrationSettingsOut, notifiedAttendees=len(to_notify))

    @staticmethod
    def _check_registration_period(event: Event, sent: dict) -> None:
        opens = sent.get("registrationOpensAt", event.registrationOpensAt)
        closes = sent.get("registrationClosesAt", event.registrationClosesAt)
        if opens and closes and closes <= opens:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Registration must close after it opens"
            )
        if closes and event.proposedStartAt and closes > event.proposedStartAt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Registration must close no later than the event starts ({_as_text(event.proposedStartAt)})",
            )

    @staticmethod
    def _venue_capacity_warnings(event: Event, capacity: int, authorization: str | None) -> list[dict]:
        warnings = []
        for venue in booked_venue_capacities(event.eventId, event.layoutPreference, authorization):
            if capacity <= venue["capacity"]:
                continue
            where = f"in the {venue['layout']} layout " if venue["layout"] else ""
            warnings.append(
                {
                    "kind": "venueCapacity",
                    "capacity": capacity,
                    "venueCapacity": venue["capacity"],
                    "venueName": venue["venueName"],
                    "layout": venue["layout"],
                    "message": f"A capacity of {capacity} is more than {venue['venueName']} holds "
                    f"{where}({venue['capacity']}).",
                }
            )
        return warnings

    def _notify_registration_change(
        self, event: Event, changes: dict, attendees: list[dict], authorization: str | None
    ) -> None:
        """Best effort: the settings are already saved."""
        summary = "; ".join(f"{FIELD_LABELS[field]}: {_setting_text(value)}" for field, value in changes.items())
        title = f"Registration settings changed for {event.eventName}"
        body = f"Your coordinator updated the registration settings for {event.eventName}. {summary}."
        organiser = self._recipient(self._directory(authorization), event.organiserId, event)
        if organiser is not None:
            send_notification(organiser["email"], title, body, authorization)
        record_notification(event.organiserId, event.eventId, "event.registration_settings", title, body, authorization)
        closed_title = f"Registration closed for {event.eventName}"
        closed_body = (
            f"Registration for {event.eventName} has been turned off. You are registered for this event, so we "
            "wanted you to know. ConnectSphere will contact you if this affects your place."
        )
        for attendee in attendees:
            send_notification(attendee["attendeeEmail"], closed_title, closed_body, authorization)
            if attendee.get("userId"):
                record_notification(
                    attendee["userId"], event.eventId, "registration.closed", closed_title, closed_body, authorization
                )

    @staticmethod
    def changeable_fields() -> ChangeableFieldsOut:
        return ChangeableFieldsOut(fields=list(CHANGEABLE_FIELDS))

    def list_change_requests(self, event_id: str, caller: dict) -> list[ChangeRequestOut]:
        """SPM-106 AC4: every change request on the event, newest first, for
        the organiser's organisation and staff."""
        event = self._require_event(event_id)
        _require_organiser_or_staff(event, caller, "change requests")
        return [_change_request_out(row) for row in self.change_request_dao.list_by_event(event.eventId)]

    def raise_change_request(
        self, event_id: str, data: ChangeRequestCreate, caller: dict, authorization: str | None = None
    ) -> ChangeRequestOut:
        """SPM-106: the organiser (or a colleague in their organisation) asks
        for a change.

        Allowed under review, approved, in planning, or confirmed (AC1); a
        draft is edited directly (AC8) and a finished event takes none (AC9).
        Each field is stored with its current and proposed value and the
        reason (AC2, AC3). Only one request may be pending (AC5). The event
        itself is not touched, so its confirmed details still read as
        confirmed (AC10). The assigned coordinator is emailed (AC4).
        """
        event = self._require_event(event_id)
        if not _is_event_organiser(event, caller):
            raise forbidden("Only the event's organisation can request a change to it")
        if event.status in ("draft", "discarded"):
            raise conflict("A draft is edited directly, so there is no change to request")
        if event.status not in CHANGE_REQUEST_STATUSES:
            raise conflict(
                "A change can be requested while the event is under review, approved, in planning, "
                f"or confirmed (this one is {event.status})"
            )
        if self.change_request_dao.has_with_status(event.eventId, PENDING):
            raise conflict("This event already has a pending change request. Withdraw it before requesting another.")
        proposed = {
            field: value
            for field, value in data.proposedChanges.items()
            if _differs(_json_value(getattr(event, field)), value)
        }
        if not proposed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The proposed values are the same as the event's current details",
            )
        start = datetime.fromisoformat(proposed["proposedStartAt"]) if "proposedStartAt" in proposed else event.proposedStartAt
        end = datetime.fromisoformat(proposed["proposedEndAt"]) if "proposedEndAt" in proposed else event.proposedEndAt
        if start and end and end <= start:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The end must be after the start")
        change_request = EventChangeRequest(
            changeRequestId=str(uuid4()),
            eventId=event.eventId,
            requestedBy=caller["userId"],
            status=PENDING,
            summary=data.reason,
            proposedChanges=proposed,
            currentValues={field: _json_value(getattr(event, field)) for field in proposed},
            affectsVenue=any(field in proposed for field in AFFECTS_VENUE),
            affectsEquipment=any(field in proposed for field in AFFECTS_EQUIPMENT),
            affectsRegistration=any(field in proposed for field in AFFECTS_REGISTRATION),
            createdAt=datetime.utcnow(),
        )
        self.change_request_dao.add(change_request)
        self.db.commit()
        self.db.refresh(change_request)
        users = self._directory(authorization)
        coordinator = self._recipient(users, event.coordinatorId, event)
        if coordinator is not None:
            send_notification(
                coordinator["email"],
                f"Change requested for {event.eventName}",
                f"{_name_of(users, change_request.requestedBy)} has asked to change {_field_list(proposed)} on "
                f"{event.eventName}. Reason: {data.reason} Review it on the event in ConnectSphere.",
                authorization,
            )
        return _change_request_out(change_request)

    def withdraw_change_request(
        self, event_id: str, change_request_id: str, caller: dict, authorization: str | None = None
    ) -> ChangeRequestOut:
        """SPM-106 AC6: the organiser who raised a pending request takes it
        back; the assigned coordinator is emailed, best effort."""
        event = self._require_event(event_id)
        change_request = self._require_change_request(event.eventId, change_request_id)
        if change_request.requestedBy != caller.get("userId"):
            raise forbidden("Only the organiser who requested the change can withdraw it")
        self._close_change_request(change_request, "withdrawn", caller["userId"])
        self.db.commit()
        self.db.refresh(change_request)
        users = self._directory(authorization)
        coordinator = self._recipient(users, event.coordinatorId, event)
        if coordinator is not None:
            send_notification(
                coordinator["email"],
                f"Change request withdrawn for {event.eventName}",
                f"{_name_of(users, change_request.requestedBy)} has withdrawn their request to change "
                f"{_field_list(change_request.proposedChanges)} on {event.eventName}. Nothing needs deciding.",
                authorization,
            )
        return _change_request_out(change_request)

    def accept_change_request(
        self,
        event_id: str,
        change_request_id: str,
        data: ChangeRequestAccept,
        coordinator_id: str,
        authorization: str | None = None,
    ) -> ChangeRequestOut:
        """SPM-106 AC7: the assigned coordinator agrees, and the proposed values
        are applied under the same rules as their own edit (SPM-71): a
        significant change touching confirmed arrangements, or a confirmed
        event, is 409 until confirmed; then the arrangements are flagged for
        re-verification and a confirmed event becomes reconsidering. Every
        applied field is logged. The organiser is told, with any reason."""
        event = self._require_event(event_id)
        _require_assigned_coordinator(event, coordinator_id, "accept a change request")
        change_request = self._require_change_request(event.eventId, change_request_id)
        self._require_pending(change_request)
        try:
            update = EventUpdate(
                **(change_request.proposedChanges or {}), confirmSignificantChange=data.confirmSignificantChange
            )
        except ValidationError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This request's proposed values cannot be applied. Decline it and ask for a new one.",
            )
        flagged = self._apply_changes(event, update, coordinator_id, authorization)
        self._close_change_request(change_request, "accepted", coordinator_id, data.reason.strip() or None)
        self.db.commit()
        self.db.refresh(change_request)
        self._notify_decision(event, change_request, authorization)
        return _change_request_out(change_request, flagged)

    def decline_change_request(
        self,
        event_id: str,
        change_request_id: str,
        data: ChangeRequestDecline,
        coordinator_id: str,
        authorization: str | None = None,
    ) -> ChangeRequestOut:
        """SPM-106 AC7: the assigned coordinator says no, with a reason the
        organiser is told. The event is unchanged."""
        event = self._require_event(event_id)
        _require_assigned_coordinator(event, coordinator_id, "decline a change request")
        change_request = self._require_change_request(event.eventId, change_request_id)
        self._close_change_request(change_request, "declined", coordinator_id, data.reason)
        self.db.commit()
        self.db.refresh(change_request)
        self._notify_decision(event, change_request, authorization)
        return _change_request_out(change_request)

    def _require_change_request(self, event_id: str, change_request_id: str) -> EventChangeRequest:
        return self._require(
            self.change_request_dao.get_for_event(event_id, change_request_id), "Change request not found"
        )

    @staticmethod
    def _require_pending(change_request: EventChangeRequest) -> None:
        if change_request.status != PENDING:
            raise conflict(f"This change request is already {change_request.status}")

    def _close_change_request(
        self, change_request: EventChangeRequest, outcome: str, closed_by: str, reason: str | None = None
    ) -> None:
        self._require_pending(change_request)
        change_request.status = outcome
        change_request.reviewedBy = closed_by
        change_request.reviewedAt = datetime.utcnow()
        change_request.decisionReason = reason

    def _notify_decision(self, event: Event, change_request: EventChangeRequest, authorization: str | None) -> None:
        """SPM-106 AC7: email and in-app notice to whoever raised it. Best effort."""
        outcome = change_request.status
        title = f"Your change request for {event.eventName} was {outcome}"
        body = (
            f"Your coordinator {outcome} your request to change {_field_list(change_request.proposedChanges)} "
            f"on {event.eventName}."
        )
        if change_request.decisionReason:
            body += f" Reason: {change_request.decisionReason}"
        if outcome == "accepted":
            body += " The event now shows the new details."
        requester = self._recipient(self._directory(authorization), change_request.requestedBy, event)
        if requester is not None:
            send_notification(requester["email"], title, body, authorization)
        record_notification(change_request.requestedBy, event.eventId, "event.change_request", title, body, authorization)

    def list_coordinator_candidates(self, authorization: str | None = None) -> list[CoordinatorCandidateOut]:
        """SPM-66 AC2: every Event Coordinator with their count of active
        events, for information only (AC3: no workload limit applies)."""
        counts = self.event_dao.count_by_coordinator_excluding_statuses(list(LOCKED_STATUSES))
        coordinators = [user for user in list_users(authorization) if user.get("role") == "coordinator"]
        return sorted(
            (
                CoordinatorCandidateOut(
                    userId=user["userId"],
                    name=user["userName"],
                    email=user["email"],
                    activeEventCount=counts.get(user["userId"], 0),
                )
                for user in coordinators
            ),
            key=lambda candidate: candidate.name.lower(),
        )

    def get_event_coordinator(
        self, event_id: str, caller: dict, authorization: str | None = None
    ) -> EventCoordinatorOut:
        """SPM-66 AC5: the organiser's one person to deal with. Organisers see
        it for their own organisation's events; staff for any event."""
        event = self._require_event(event_id)
        _require_organiser_or_staff(event, caller, "coordinator")
        if not event.coordinatorId:
            return EventCoordinatorOut(eventId=event.eventId)
        user = next((row for row in list_users(authorization) if row["userId"] == event.coordinatorId), None)
        return EventCoordinatorOut(
            eventId=event.eventId,
            coordinatorId=event.coordinatorId,
            name=user["userName"] if user else None,
            email=user["email"] if user else None,
        )

    def assign_coordinator(
        self,
        event_id: str,
        data: EventAssignmentCreate,
        assigned_by: str,
        authorization: str | None = None,
    ) -> EventAssignmentOut:
        """SPM-66: assign (or reassign) the event's coordinator.

        The assignee must be an Event Coordinator (AC8); there is no workload
        limit (AC3). The assignment row records who assigned whom and when and
        appears in the activity log (AC4). A submitted request moves to
        "under review" (AC6). The new coordinator and the organiser are
        notified (AC5) after the save, best effort.
        """
        event = self._require_event(event_id)
        if event.status in LOCKED_STATUSES:
            raise conflict(f"A {event.status} event cannot be assigned a coordinator")
        users = {user["userId"]: user for user in list_users(authorization)}
        assignee = users.get(data.coordinatorId)
        if assignee is None or assignee.get("role") != "coordinator":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An event can only be assigned to an Event Coordinator",
            )
        now = datetime.utcnow()
        row = EventAssignment(
            assignmentId=str(uuid4()),
            eventId=event_id,
            coordinatorId=data.coordinatorId,
            assignedBy=assigned_by,
            assignedAt=now,
        )
        self.assignment_dao.add(row)
        event.coordinatorId = data.coordinatorId
        if event.status == "submitted":
            self._record_status_change(event, "under review", assigned_by, f"Assigned to {assignee['userName']}", now)
            event.status = "under review"
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(row)
        self._notify_assignment(event, assignee, users.get(event.organiserId), authorization)
        return EventAssignmentOut(
            assignmentId=row.assignmentId,
            eventId=row.eventId,
            coordinatorId=row.coordinatorId,
            assignedBy=row.assignedBy,
            assignedAt=row.assignedAt,
        )

    @staticmethod
    def _notify_assignment(
        event: Event, assignee: dict, organiser: dict | None, authorization: str | None
    ) -> None:
        send_notification(
            assignee["email"],
            f"You are now the coordinator for {event.eventName}",
            f"{event.eventName} has been assigned to you. It is currently {event.status}.",
            authorization,
        )
        if organiser is None:
            logger.warning("organiser %s of event %s not in the user directory", event.organiserId, event.eventId)
            return
        send_notification(
            organiser["email"],
            f"Your coordinator for {event.eventName}",
            f"{assignee['userName']} is now your coordinator for {event.eventName}. "
            f"You can reach them at {assignee['email']}.",
            authorization,
        )

    def _record_status_change(
        self,
        event: Event,
        to_status: str,
        changed_by: str,
        note: str = "",
        at: datetime | None = None,
    ) -> None:
        self.history_dao.add(
            EventStatusHistory(
                historyId=str(uuid4()),
                eventId=event.eventId,
                fromStatus=event.status,
                toStatus=to_status,
                changedBy=changed_by,
                note=note,
                createdAt=at or datetime.utcnow(),
            )
        )

    def _decide_event(
        self,
        event_id: str,
        coordinator_id: str,
        new_status: str,
        reason: str,
        authorization: str | None = None,
    ) -> EventOut:
        event = self._require_event(event_id)
        if event.status not in DECIDABLE_STATUSES:
            raise conflict(f"Event is already {event.status}")
        self._record_status_change(event, new_status, coordinator_id, reason)
        event.status = new_status
        event.updatedAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(event)
        if new_status in ("rejected", "cancelled", "completed"):
            release_event_holds(event.eventId, authorization)
        return _to_out(event, authorization)

    def approve_event(
        self,
        event_id: str,
        coordinator_id: str,
        note: str = "",
        confirm_open_clarifications: bool = False,
        authorization: str | None = None,
    ) -> EventApprovalOut:
        """SPM-69: the assigned coordinator takes the request on.

        Only the assigned coordinator can approve, and only once the request is
        under review (AC1); with no coordinator yet there is nothing to approve
        (AC5). While clarifications are open the coordinator must confirm
        first (AC4). Approval moves the event to planning and stores the
        decision, decider, time, and note as an `approve` review, plus a status
        change for the activity log (AC2). The note stays out of the activity
        log, which attendees can read. The organiser is emailed after the save,
        best effort (AC3). Nothing here calls venue-service or
        equipment-service, so no venue or equipment is held and those
        arrangements stay outstanding (AC6).
        """
        event = self._require_event(event_id)
        _require_assigned_coordinator(event, coordinator_id, "approve it")
        if event.status not in IN_REVIEW_STATUSES:
            raise conflict(f"Only a request under review can be approved (this one is {event.status})")
        if _has_open_clarifications(event) and not confirm_open_clarifications:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "This request still has open clarifications with the organiser. "
                    "Confirm to approve it anyway.",
                    "requiresConfirmation": True,
                    "openClarifications": True,
                },
            )
        note = note.strip()
        now = datetime.utcnow()
        self.review_dao.add(
            EventReview(
                reviewId=str(uuid4()),
                eventId=event.eventId,
                reviewerId=coordinator_id,
                action="approve",
                comment=note,
                createdAt=now,
            )
        )
        self._record_status_change(event, "planning", coordinator_id, "Approved", now)
        event.status = "planning"
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(event)
        self._notify_approval(event, note, authorization)
        return _to_out(
            event,
            authorization,
            out_type=EventApprovalOut,
            decisionNote=note,
            decidedBy=coordinator_id,
            decidedAt=now,
        )

    @staticmethod
    def _directory(authorization: str | None) -> dict[str, dict]:
        """userId -> user, best effort: callers have already saved their change,
        or only need names for display, so an unreachable directory is empty."""
        try:
            return {user["userId"]: user for user in list_users(authorization)}
        except HTTPException:
            logger.warning("user directory unavailable; names and emails skipped")
            return {}

    @staticmethod
    def _recipient(users: dict[str, dict], user_id: str | None, event: Event) -> dict | None:
        recipient = users.get(user_id) if user_id else None
        if recipient is None:
            logger.warning("no directory entry for %s on event %s; not notified", user_id, event.eventId)
        return recipient

    def _notify_approval(self, event: Event, note: str, authorization: str | None) -> None:
        """Best effort: the approval is already saved, so a directory or email
        failure is logged rather than raised."""
        organiser = self._recipient(self._directory(authorization), event.organiserId, event)
        if organiser is None:
            return
        body = (
            f"ConnectSphere has approved {event.eventName} and taken it on, so planning has started. "
            "No venue or equipment has been booked yet; your coordinator will arrange those next."
        )
        if note:
            body += f" Note from your coordinator: {note}"
        send_notification(organiser["email"], f"{event.eventName} has been approved", body, authorization)

    def get_event_decision(self, event_id: str, caller: dict) -> EventDecisionOut:
        """SPM-69 AC3: the outcome and note the organiser sees on their event.
        Kept off GET /events/{id}, which attendees can read too."""
        event = self._require_event(event_id)
        _require_organiser_or_staff(event, caller, "decision")
        review = self.review_dao.latest_with_action(event.eventId, list(DECISIONS))
        if review is None:
            return EventDecisionOut(eventId=event.eventId)
        return EventDecisionOut(
            eventId=event.eventId,
            decision=DECISIONS[review.action],
            decisionNote=review.comment,
            decidedBy=review.reviewerId,
            decidedAt=review.createdAt,
        )

    def list_clarifications(
        self, event_id: str, caller: dict, authorization: str | None = None
    ) -> list[ClarificationOut]:
        """SPM-68: every clarification thread on the event, oldest first (AC3).
        The organiser's organisation and staff can read them at any stage,
        including after the event is confirmed, completed, or cancelled (AC7);
        attendees never can (AC6)."""
        event = self._require_event(event_id)
        _require_organiser_or_staff(event, caller, "clarifications")
        users = self._directory(authorization)
        return [
            self._clarification_out(row, users)
            for row in self.review_dao.list_with_replies(event.eventId, CLARIFICATION)
        ]

    def raise_clarification(
        self,
        event_id: str,
        data: ClarificationCreate,
        coordinator_id: str,
        authorization: str | None = None,
    ) -> ClarificationOut:
        """SPM-68: the assigned coordinator asks the organiser about the request.

        Each clarification is tracked as open or resolved on its own (AC4), so
        more than one can be open. Raising one moves the request to changes
        requested and emails the organiser after the save, best effort (AC2).
        A draft is not a request yet, so it cannot take one (AC8). The question
        stays out of the activity log, which attendees can read (AC6).
        """
        event = self._require_event(event_id)
        if event.status in ("draft", "discarded"):
            raise conflict(f"A {event.status} event is not a request yet, so no clarification can be raised against it")
        _require_assigned_coordinator(event, coordinator_id, "raise a clarification")
        if event.status not in IN_REVIEW_STATUSES:
            raise conflict(f"Clarifications can only be raised while the request is under review (this one is {event.status})")
        now = datetime.utcnow()
        clarification = EventReview(
            reviewId=str(uuid4()),
            eventId=event.eventId,
            reviewerId=coordinator_id,
            action=CLARIFICATION,
            comment=data.message,
            field=data.field,
            status=OPEN,
            createdAt=now,
        )
        self.review_dao.add(clarification)
        if event.status != AWAITING_CLARIFICATION:
            self._record_status_change(event, AWAITING_CLARIFICATION, coordinator_id, "Clarification requested", now)
            event.status = AWAITING_CLARIFICATION
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(clarification)
        users = self._directory(authorization)
        organiser = self._recipient(users, event.organiserId, event)
        if organiser is not None:
            about = f" ({FIELD_LABELS[data.field]})" if data.field else ""
            send_notification(
                organiser["email"],
                f"Your coordinator has a question about {event.eventName}",
                f"Your coordinator needs more information about {event.eventName}{about}: {data.message} "
                "Please reply on the event in ConnectSphere so the conversation stays with your request.",
                authorization,
            )
        return self._clarification_out(clarification, users)

    def reply_to_clarification(
        self,
        event_id: str,
        clarification_id: str,
        data: ClarificationReplyCreate,
        caller: dict,
        authorization: str | None = None,
    ) -> ClarificationOut:
        """SPM-68 AC3: the organiser (or a colleague in their organisation) or
        the assigned coordinator adds to an open thread. The other side is
        emailed after the save, best effort."""
        event = self._require_event(event_id)
        clarification = self._require_clarification(event.eventId, clarification_id)
        coordinator = caller.get("role") == "coordinator" and caller.get("userId") == event.coordinatorId
        if not (coordinator or _is_event_organiser(event, caller)):
            raise forbidden("Only the event's organiser or its assigned coordinator can reply to a clarification")
        if clarification.status == RESOLVED:
            raise conflict("This clarification is resolved, so it can no longer be replied to")
        self.review_dao.add(
            EventClarificationReply(
                replyId=str(uuid4()),
                reviewId=clarification.reviewId,
                authorId=caller["userId"],
                authorRole=caller["role"],
                message=data.message,
                createdAt=datetime.utcnow(),
            )
        )
        self.db.commit()
        self.db.refresh(clarification)
        users = self._directory(authorization)
        recipient = self._recipient(users, event.organiserId if coordinator else event.coordinatorId, event)
        if recipient is not None:
            body = f"There is a new reply about {event.eventName}: {data.message}"
            if not coordinator and event.status not in IN_REVIEW_STATUSES:
                # SPM-06 AC4: a late answer still reaches the coordinator, flagged as such.
                body += f" This request is no longer awaiting review; it is now {event.status}."
            send_notification(recipient["email"], f"New reply on a clarification for {event.eventName}", body, authorization)
        return self._clarification_out(clarification, users)

    def resolve_clarification(
        self,
        event_id: str,
        clarification_id: str,
        coordinator_id: str,
        authorization: str | None = None,
    ) -> ClarificationOut:
        """SPM-68 AC5: the assigned coordinator closes one clarification. Once
        none is open, a request waiting on the organiser returns to under
        review; an event that has moved on keeps its status."""
        event = self._require_event(event_id)
        clarification = self._require_clarification(event.eventId, clarification_id)
        _require_assigned_coordinator(event, coordinator_id, "resolve a clarification")
        if clarification.status == RESOLVED:
            raise conflict("This clarification is already resolved")
        now = datetime.utcnow()
        clarification.status = RESOLVED
        clarification.resolvedBy = coordinator_id
        clarification.resolvedAt = now
        # `clarification` is the same object as its entry in event.reviews, so
        # this already counts it as resolved.
        if event.status == AWAITING_CLARIFICATION and not _has_open_clarifications(event):
            self._record_status_change(event, "under review", coordinator_id, "All clarifications resolved", now)
            event.status = "under review"
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(clarification)
        return self._clarification_out(clarification, self._directory(authorization))

    def _require_clarification(self, event_id: str, clarification_id: str) -> EventReview:
        return self._require(
            self.review_dao.get_with_action(event_id, clarification_id, CLARIFICATION), "Clarification not found"
        )

    @staticmethod
    def _clarification_out(clarification: EventReview, users: dict[str, dict]) -> ClarificationOut:
        def name(user_id: str) -> str | None:
            return users.get(user_id, {}).get("userName")

        question = ClarificationEntryOut(
            entryId=clarification.reviewId,
            authorId=clarification.reviewerId,
            authorName=name(clarification.reviewerId),
            authorRole="coordinator",
            message=clarification.comment,
            createdAt=clarification.createdAt,
        )
        replies = [
            ClarificationEntryOut(
                entryId=reply.replyId,
                authorId=reply.authorId,
                authorName=name(reply.authorId),
                authorRole=reply.authorRole,
                message=reply.message,
                createdAt=reply.createdAt,
            )
            for reply in clarification.replies
        ]
        return ClarificationOut(
            clarificationId=clarification.reviewId,
            eventId=clarification.eventId,
            message=clarification.comment,
            field=clarification.field,
            status=clarification.status,
            raisedBy=clarification.reviewerId,
            createdAt=clarification.createdAt,
            resolvedBy=clarification.resolvedBy,
            resolvedAt=clarification.resolvedAt,
            entries=[question, *replies],
        )

    def reject_event(
        self,
        event_id: str,
        coordinator_id: str,
        reason: str = "",
        authorization: str | None = None,
    ) -> EventOut:
        return self._decide_event(event_id, coordinator_id, "rejected", reason, authorization)

    def complete_event(
        self, event_id: str, coordinator_id: str, authorization: str | None = None
    ) -> EventOut:
        """SPM-73: the assigned coordinator closes out a confirmed event once
        it has taken place (AC1).

        Completing is just a status change (AC2, recorded via the same
        _record_status_change history every other transition uses - that
        history is what the activity log reads, so "who and when" needs no
        extra column on Event). Everything downstream already keys off
        event.status, so nothing else has to be touched for this one write:
        - AC3 (venue/equipment availability): venue-service and
          equipment-service only ever check bookings/reservations against a
          *future* window, so a booking whose own dates are already in the
          past - which is guaranteed here, since AC1 requires proposedEndAt
          to have passed - never overlaps a future availability check,
          whatever its own status says. No cross-service call needed.
        - AC4 (stays readable): get_event/get_activity_log never filter by
          status, so a completed event is still readable, log and all.
        - AC5 (hidden from active views by default, filterable back): every
          status-scoped list (queue, confirmed, upcoming) matches a specific
          status/status set that no longer includes this event once its
          status is "completed" - that happens for free as soon as the
          status changes. /events/all already includes every non-draft,
          non-rejected, non-discarded status (completed included), and
          /events/{id} always works - so "filter back into view" already
          exists; nothing new to add.
        - AC6 (no more registering/withdrawing): registration-service's
          eligibility() already requires status == "confirmed", and its
          _CLOSED_EVENT_STATUSES already includes "completed" for the
          withdrawal check - both already written, unused only because
          nothing ever set this status before now.
        """
        event = self._require_event(event_id)
        if event.coordinatorId != coordinator_id:
            raise forbidden("Only the event's assigned coordinator can mark it completed")
        if event.status != "confirmed":
            raise conflict(f"Only a confirmed event can be marked completed (this one is {event.status})")
        if event.proposedEndAt is None or event.proposedEndAt > datetime.utcnow():
            raise conflict("This event cannot be marked completed until its end time has passed")
        self._record_status_change(event, "completed", coordinator_id)
        event.status = "completed"
        event.updatedAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(event)
        release_event_holds(event.eventId, authorization)
        return _to_out(event, authorization)

    # SPM-120: safety review --------------------------------------------------

    def submit_safety_review(
        self, event_id: str, data: SafetySubmission, coordinator_id: str, authorization: str | None = None
    ) -> SafetyReviewOut:
        """SPM-120: the assigned coordinator sends a planning event to the
        Safety Officers with both notes at once, for example after revising
        rejected arrangements (AC9). Venue Staff and technical support usually
        send their parts instead (`send_venue_arrangements`); this replaces any
        part already sent.

        Only once its venue booking and its technical arrangements are
        confirmed (AC1). The venue, equipment, and event facts are copied into
        the review with the crowd-movement and placement notes, so the officer
        judges exactly what was sent (AC2). The event moves to `safety review`,
        and every Safety Officer is told, best effort.
        """
        event = self._require_event(event_id)
        _require_assigned_coordinator(event, coordinator_id, "submit it for a safety review")
        if event.status not in SAFETY_SUBMITTABLE_STATUSES:
            raise conflict(f"An event is submitted for a safety review from planning (this one is {event.status})")
        review = self._open_safety_review(event, data, coordinator_id, "Submitted for safety review", authorization)
        return _safety_review_out(review)

    def safety_handoff(self, event_id: str, caller: dict, authorization: str | None = None) -> SafetyHandoffOut:
        """SPM-120, change 6: which arrangements have been sent to the Safety
        Officer this round, and whether the event needs technical ones at all."""
        event = self._require_event(event_id)
        _require_organiser_or_staff(event, caller, "safety reviews")
        arrangements = self._check_arrangements(event, authorization)
        needed = technical_needed(event.equipmentLines or [], arrangements.requests, arrangements.reservations)
        return _handoff_out(event.eventId, self.handoff_dao.get(event.eventId), needed)

    def send_venue_arrangements(
        self, event_id: str, data: SafetyVenueHandoff, sender_id: str, authorization: str | None = None
    ) -> SafetyHandoffOut:
        """SPM-120, change 6: Venue Staff send the confirmed venue arrangements
        to the Safety Officer, with how the crowd moves. Every requested venue
        must be approved for the event's date and time."""
        return self._send_arrangements(event_id, "venue", data.crowdMovement, sender_id, authorization)

    def send_technical_arrangements(
        self, event_id: str, data: SafetyTechnicalHandoff, sender_id: str, authorization: str | None = None
    ) -> SafetyHandoffOut:
        """SPM-120, change 6: technical support send the confirmed technical
        arrangements, with where the equipment goes. Every equipment line must
        be reserved or recorded as not required."""
        return self._send_arrangements(event_id, "equipment", data.equipmentPlacement, sender_id, authorization)

    def _send_arrangements(
        self, event_id: str, kind: str, note: str, sender_id: str, authorization: str | None
    ) -> SafetyHandoffOut:
        """Record one part, then open the review once every part the event
        needs is in. The other part, if its arrangements changed since it was
        sent, is cleared and must be sent again."""
        event = self._require_event(event_id)
        if event.status not in SAFETY_SUBMITTABLE_STATUSES:
            raise conflict(f"Arrangements are sent to the Safety Officer from planning (this one is {event.status})")
        arrangements = self._check_arrangements(event, authorization)
        needed = technical_needed(event.equipmentLines or [], arrangements.requests, arrangements.reservations)
        if kind == "equipment" and not needed:
            raise conflict("This event has no equipment, so there are no technical arrangements to send.")
        own = [gap for gap in arrangements.gaps if gap["kind"] == kind]
        if own:
            raise _missing(own)
        handoff = self.handoff_dao.get(event.eventId)
        if handoff is None:
            handoff = EventSafetyHandoff(eventId=event.eventId)
            self.handoff_dao.add(handoff)
            # Written now, so opening the review below finds it and removes it.
            self.db.flush()
        _set_part(handoff, kind, note, sender_id, datetime.utcnow())
        other = "equipment" if kind == "venue" else "venue"
        if any(gap["kind"] == other for gap in arrangements.gaps):
            _set_part(handoff, other, None, None, None)
        out = _handoff_out(event.eventId, handoff, needed)
        if handoff.venueSentAt and (handoff.technicalSentAt or not needed):
            data = SafetySubmission(crowdMovement=handoff.crowdMovement, equipmentPlacement=handoff.equipmentPlacement or "")
            review = self._open_safety_review(
                event, data, sender_id, "Arrangements sent for safety review", authorization, arrangements
            )
            self._notify_review_opened(event, authorization)
            out.review = _safety_review_out(review)
        else:
            self.db.commit()
        return out

    def _open_safety_review(
        self,
        event: Event,
        data: SafetySubmission,
        submitted_by: str,
        note: str,
        authorization: str | None,
        arrangements: "Arrangements | None" = None,
    ) -> EventSafetyReview:
        """Take the package, start the review, and tell every Safety Officer.
        Arrangements sent separately this round are now part of it."""
        package = self._safety_package(event, data, authorization, arrangements)
        now = datetime.utcnow()
        review = EventSafetyReview(
            reviewId=str(uuid4()),
            eventId=event.eventId,
            status=PENDING,
            submittedBy=submitted_by,
            submittedAt=now,
            crowdMovement=data.crowdMovement,
            equipmentPlacement=data.equipmentPlacement,
            package=package,
        )
        self.safety_dao.add(review)
        handoff = self.handoff_dao.get(event.eventId)
        if handoff is not None:
            self.handoff_dao.delete(handoff)
        self._record_status_change(event, SAFETY_REVIEW, submitted_by, note, now)
        event.status = SAFETY_REVIEW
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(review)
        self._notify_safety_officers(event, authorization)
        return review

    @staticmethod
    def _check_arrangements(event: Event, authorization: str | None) -> "Arrangements":
        """The venue and equipment rules shared by the safety review gate
        (SPM-120) and confirmation (SPM-72). Reads are strict: an arrangement
        that cannot be checked is never treated as confirmed."""
        bookings = event_bookings(event.eventId, authorization)
        requests = equipment_requests_for(event.eventId, authorization)
        reservations = equipment_reservations_for(event.eventId, authorization)
        lines = list(event.equipmentLines or [])
        names = equipment_names(authorization) if requests or lines else {}
        gaps = venue_gaps(bookings, event.proposedStartAt, event.proposedEndAt) + equipment_gaps(
            lines, requests, reservations, names
        )
        return Arrangements(gaps, bookings, requests, reservations, names)

    def _safety_package(
        self,
        event: Event,
        data: SafetySubmission,
        authorization: str | None,
        arrangements: "Arrangements | None" = None,
    ) -> dict:
        """AC1's gate, then AC2's facts. Every requested venue must be approved
        for the event's date and time, and every equipment line reserved or
        recorded as not required. A booking flagged for re-checking still counts
        while it covers the event's time, because nothing can clear the flag
        yet (SPM-86); the flag is shown to the officer instead."""
        if arrangements is None:
            arrangements = self._check_arrangements(event, authorization)
        if arrangements.gaps:
            raise _missing(arrangements.gaps)
        bookings = [row for row in arrangements.bookings if row.get("status") == "approved"]
        reservations, names = arrangements.reservations, arrangements.names
        lines = requested_lines(arrangements.requests)
        if technical_needed(event.equipmentLines or [], arrangements.requests, reservations) and not data.equipmentPlacement:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Say where the reserved equipment will be placed.",
            )
        flagged_requests = {row.get("requestId") for row in reservations if row.get("needsReverification")}
        venues = []
        for booking in bookings:
            venue = venue_details(booking["venueId"], authorization)
            by_layout = {row["name"].lower(): row["capacity"] for row in venue.get("layouts", [])}
            wanted = (event.layoutPreference or "").lower()
            layout = event.layoutPreference if wanted in by_layout else None
            venues.append(
                SafetyVenueFacts(
                    venueId=venue["venueId"],
                    venueName=venue["name"],
                    location=venue.get("location") or "",
                    startsAt=booking["startsAt"],
                    endsAt=booking["endsAt"],
                    layout=layout,
                    capacityInLayout=by_layout[wanted] if layout else venue["capacity"],
                    venueCapacity=venue["capacity"],
                    layouts=venue.get("layouts", []),
                    accessibilityFeatures=venue.get("accessibility", []),
                    emergencyAccess=venue.get("emergencyAccess") or "",
                    restrictions=venue.get("restrictions") or "",
                    operatingHours=venue.get("operatingHours", []),
                    needsReverification=bool(booking.get("needsReverification")),
                    reverificationNote=booking.get("reverificationNote"),
                )
            )
        accessibility = list(event.accessibilitySelections or []) or (
            [event.accessibilityNeeds] if event.accessibilityNeeds else []
        )
        return SafetyPackage(
            eventName=event.eventName,
            proposedStartAt=event.proposedStartAt,
            proposedEndAt=event.proposedEndAt,
            expectedAttendance=event.expectedAttendance,
            layout=event.layoutPreference,
            accessibilityRequirements=accessibility,
            accessibilityNote=event.accessibilityNote or "",
            venues=venues,
            equipment=[
                SafetyEquipmentLine(
                    equipmentId=row["equipmentId"],
                    name=names.get(row["equipmentId"], row["equipmentId"]),
                    quantity=row["quantity"],
                    status=row["status"],
                    technicalRequirements=row.get("technicalRequirements") or "",
                    needsReverification=row.get("requestId") in flagged_requests,
                )
                for row in lines
            ],
            crowdMovement=data.crowdMovement,
            equipmentPlacement=data.equipmentPlacement,
        ).model_dump(mode="json")

    def list_safety_reviews(self, review_status: str = PENDING) -> list[SafetyReviewOut]:
        """The Safety Officers' queue, longest-waiting first."""
        return [_safety_review_out(row) for row in self.safety_dao.list_with_status(review_status)]

    def get_safety_reviews(self, event_id: str, caller: dict) -> list[SafetyReviewOut]:
        """Every safety review of the event, newest first, for the organiser's
        organisation and staff (AC9: the organiser sees the outcome)."""
        event = self._require_event(event_id)
        _require_organiser_or_staff(event, caller, "safety reviews")
        return [_safety_review_out(row) for row in self.safety_dao.list_by_event(event.eventId)]

    def approve_safety_review(
        self, event_id: str, review_id: str, data: SafetyApproval, officer_id: str, authorization: str | None = None
    ) -> SafetyReviewOut:
        """AC3/AC4: the plan is safe. The decision, the officer, and the time
        are recorded, and the event waits for the coordinator to confirm it
        (SPM-72); preparation begins once it is confirmed."""
        event, review = self._pending_safety_review(event_id, review_id)
        now = datetime.utcnow()
        self._close_safety_review(review, "approved", officer_id, data.note.strip() or None, now)
        self._record_status_change(event, SAFETY_APPROVED, officer_id, "Safety review approved", now)
        event.status = SAFETY_APPROVED
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(review)
        self._notify_safety_decision(event, review, authorization)
        return _safety_review_out(review)

    def reject_safety_review(
        self, event_id: str, review_id: str, data: SafetyRejection, officer_id: str, authorization: str | None = None
    ) -> SafetyReviewOut:
        """AC5/AC9: the plan is unsafe. The reason is recorded and the event
        returns to planning, so it does not proceed to preparation, but it is
        not cancelled: the coordinator can revise the arrangements and submit
        again. The coordinator and the organiser are told."""
        event, review = self._pending_safety_review(event_id, review_id)
        now = datetime.utcnow()
        self._close_safety_review(review, "rejected", officer_id, data.reason, now)
        self._record_status_change(event, "planning", officer_id, "Safety review rejected", now)
        event.status = "planning"
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(review)
        self._notify_safety_decision(event, review, authorization)
        return _safety_review_out(review)

    def request_safety_changes(
        self,
        event_id: str,
        review_id: str,
        data: SafetyChangeRequest,
        officer_id: str,
        authorization: str | None = None,
    ) -> SafetyReviewOut:
        """AC6: what must change is recorded and the event returns to planning.
        The arrangements the officer names are flagged for re-checking, so
        venue staff or technical support review them again; the flags go out
        before the save, so a change never returns without them."""
        event, review = self._pending_safety_review(event_id, review_id)
        reason = f"Safety review: {data.requiredChanges}"
        flagged: list[dict] = []
        if "venue" in data.affected:
            flagged += flag_venue_arrangements(event.eventId, reason, authorization)
        if "technical" in data.affected:
            flagged += flag_technical_arrangements(event.eventId, reason, authorization)
        now = datetime.utcnow()
        self._close_safety_review(review, "changes_requested", officer_id, data.requiredChanges, now)
        review.affected = list(data.affected)
        self._record_status_change(event, "planning", officer_id, "Safety review: changes requested", now)
        event.status = "planning"
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(review)
        self._notify_safety_decision(event, review, authorization)
        return _safety_review_out(review, flagged)

    def _pending_safety_review(self, event_id: str, review_id: str) -> tuple[Event, EventSafetyReview]:
        event = self._require_event(event_id)
        review = self._require(
            next((row for row in self.safety_dao.list_by_event(event.eventId) if row.reviewId == review_id), None),
            "Safety review not found",
        )
        if review.status != PENDING:
            raise conflict(f"This safety review is already {review.status.replace('_', ' ')}")
        return event, review

    @staticmethod
    def _close_safety_review(
        review: EventSafetyReview, outcome: str, decided_by: str, note: str | None, now: datetime
    ) -> None:
        review.status = outcome
        review.decidedBy = decided_by
        review.decidedAt = now
        review.decisionNote = note

    def _supersede_safety_review(self, event: Event, changed_by: str, summary: str, now: datetime) -> None:
        """A significant change during the review, or after approval but before
        confirmation (SPM-72), withdraws it, and the event goes back to planning
        to be submitted again. An approval stays in the history as it was given."""
        review = self.safety_dao.pending_for_event(event.eventId)
        if review is not None:
            self._close_safety_review(review, "superseded", changed_by, summary, now)
        withdrawn = "Safety approval withdrawn" if event.status == SAFETY_APPROVED else "Safety review withdrawn"
        self._record_status_change(event, "planning", changed_by, f"{withdrawn}. {summary}", now)
        event.status = "planning"

    def _notify_safety_officers(self, event: Event, authorization: str | None) -> None:
        """Best effort: the submission is already saved."""
        title = f"{event.eventName} is ready for a safety review"
        body = f"The venue and equipment for {event.eventName} are confirmed and have been sent for a safety review."

        for officer in self._directory(authorization).values():
            if officer.get("role") != "safety":
                continue
            send_notification(officer["email"], title, body, authorization)
            record_notification(officer["userId"], event.eventId, "event.safety_review", title, body, authorization)

    def _notify_review_opened(self, event: Event, authorization: str | None) -> None:
        """SPM-120, change 6, best effort: the coordinator did not send it
        themselves, so they are told the safety review has started."""
        title = f"{event.eventName} is with the Safety Officer"
        body = f"The arrangements for {event.eventName} were sent to the Safety Officer, and its safety review has started."
        recipient = self._recipient(self._directory(authorization), event.coordinatorId, event)
        if recipient is not None:
            send_notification(recipient["email"], title, body, authorization)
        record_notification(event.coordinatorId, event.eventId, "event.safety_review", title, body, authorization)

    def _notify_safety_decision(self, event: Event, review: EventSafetyReview, authorization: str | None) -> None:
        """AC9: the assigned coordinator and the organiser, by email and in-app. Best effort."""
        if review.status == "approved":
            title = f"{event.eventName} passed its safety review"
            body = (
                f"The safety officer approved the plan for {event.eventName}. The coordinator can now confirm it, "
                "and preparation begins once it is confirmed."
            )
            if review.decisionNote:
                body += f" Note: {review.decisionNote}"
        elif review.status == "rejected":
            title = f"{event.eventName} did not pass its safety review"
            body = (
                f"The safety officer rejected the plan for {event.eventName}. Reason: {review.decisionNote} "
                "The event is not cancelled: the coordinator can revise the arrangements and submit it again."
            )
        else:
            title = f"Changes needed before {event.eventName} passes its safety review"
            body = f"The safety officer asked for these changes to {event.eventName}: {review.decisionNote}"
            if review.affected:
                body += f" Flagged for re-checking: {', '.join(review.affected)} arrangements."
            body += " The event is back in planning until it is submitted again."
        users = self._directory(authorization)
        for user_id in dict.fromkeys(user for user in (event.coordinatorId, event.organiserId) if user):
            recipient = self._recipient(users, user_id, event)
            if recipient is not None:
                send_notification(recipient["email"], title, body, authorization)
            record_notification(user_id, event.eventId, "event.safety_review", title, body, authorization)

    # SPM-72: confirm an event -------------------------------------------------

    def confirmation(self, event_id: str, coordinator_id: str, authorization: str | None = None) -> ConfirmationOut:
        """SPM-72 AC2: whether the assigned coordinator can confirm the event
        now, and if not, everything that is missing."""
        event = self._require_event(event_id)
        _require_assigned_coordinator(event, coordinator_id, "confirm it")
        gaps, _ = self._confirmation_gaps(event, authorization)
        return ConfirmationOut(eventId=event.eventId, ready=not gaps, missing=[ConfirmationGap(**gap) for gap in gaps])

    def confirm_event(self, event_id: str, coordinator_id: str, authorization: str | None = None) -> EventConfirmOut:
        """SPM-72: the assigned coordinator confirms the event so it can start
        officially.

        Only once the Safety Officer has approved it (SPM-120), and only while
        every requested venue is approved for its date and time and every
        equipment line is reserved or recorded as not required, checked again
        now rather than taken from the safety review (AC1). Anything missing is
        a 409 naming it (AC2). Confirming records who and when (AC3), tells the
        organiser (AC4) and the venue staff and technical support who handled
        the arrangements (AC5). A confirmed event with registration enabled is
        listed for attendees once its period opens (AC6).
        """
        event = self._require_event(event_id)
        _require_assigned_coordinator(event, coordinator_id, "confirm it")
        gaps, arrangements = self._confirmation_gaps(event, authorization)
        if gaps:
            raise _missing(gaps)
        now = datetime.utcnow()
        self._record_status_change(event, "confirmed", coordinator_id, "Confirmed", now)
        event.status = "confirmed"
        event.confirmedBy = coordinator_id
        event.confirmedAt = now
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(event)
        self._notify_confirmation(event, arrangements, authorization)
        return _to_out(event, authorization, out_type=EventConfirmOut, decidedBy=coordinator_id, decidedAt=now)

    def _confirmation_gaps(self, event: Event, authorization: str | None) -> tuple[list[dict], Arrangements | None]:
        """Everything standing between the event and Confirmed: its stage, its
        safety review, and its arrangements."""
        if event.status == "confirmed":
            return [{"kind": "status", "message": "This event is already confirmed."}], None
        if event.status not in (*SAFETY_SUBMITTABLE_STATUSES, SAFETY_REVIEW, SAFETY_APPROVED):
            return [
                {
                    "kind": "status",
                    "message": f"Only an event that has passed its safety review can be confirmed. This one is {event.status}.",
                }
            ], None
        arrangements = self._check_arrangements(event, authorization)
        safety = self._safety_gap(event)
        return arrangements.gaps + ([safety] if safety else []), arrangements

    def _safety_gap(self, event: Event) -> dict | None:
        """SPM-121 AC4: confirm stays unavailable while the safety check is
        outstanding, rejected, or returned for changes."""
        if event.status == SAFETY_APPROVED:
            return None
        if event.status == SAFETY_REVIEW:
            return {"kind": "safety", "message": "The Safety Officer has not reviewed it yet."}
        latest = next(iter(self.safety_dao.list_by_event(event.eventId)), None)
        handoff = self.handoff_dao.get(event.eventId)
        if handoff is not None and handoff.venueSentAt:
            message = (
                "Venue Staff have sent the venue arrangements for the safety review. Waiting on technical support "
                "to send the technical arrangements."
            )
        elif handoff is not None and handoff.technicalSentAt:
            message = (
                "Technical support have sent the technical arrangements for the safety review. Waiting on Venue "
                "Staff to send the venue arrangements."
            )
        elif latest is None:
            message = (
                "It has not been sent for a safety review yet. Venue Staff and technical support send their "
                "arrangements once they are confirmed."
            )
        elif latest.status == "rejected":
            message = f"The safety review was rejected: {latest.decisionNote} Revise the arrangements and submit it again."
        elif latest.status == "changes_requested":
            message = f"The Safety Officer asked for changes: {latest.decisionNote} Submit it again once they are made."
        else:
            message = "It needs a new safety review because the event changed. Submit it again."
        return {"kind": "safety", "message": message}

    def _notify_confirmation(self, event: Event, arrangements: Arrangements, authorization: str | None) -> None:
        """AC4/AC5, best effort: the organiser, and the venue staff and technical
        support who approved this event's bookings and equipment."""
        venues = [row for row in arrangements.bookings if row.get("status") == "approved"]
        venue_names = ", ".join(row.get("venueName") or row["venueId"] for row in venues)
        when = _setting_text(event.proposedStartAt)
        # What was requested, then any line on the event not requested and not recorded as not required.
        quantities: dict[str, int] = {}
        for row in requested_lines(arrangements.requests):
            quantities[row["equipmentId"]] = quantities.get(row["equipmentId"], 0) + int(row["quantity"])
        for line in event.equipmentLines or []:
            if not line.get("notRequired"):
                quantities.setdefault(line["equipmentId"], int(line["quantity"]))
        equipment = ", ".join(
            f"{quantity} × {arrangements.names.get(equipment_id, equipment_id)}"
            for equipment_id, quantity in quantities.items()
        )
        title = f"{event.eventName} is confirmed"
        body = (
            f"{event.eventName} is confirmed for {when} at {venue_names}. "
            f"Layout: {event.layoutPreference or 'not set'}. Equipment: {equipment or 'none'}."
        )
        if event.registrationEnabled:
            body += f" Registration opens {_setting_text(event.registrationOpensAt)}."
        staff_body = f"{event.eventName}, which you arranged for, is confirmed for {when} at {venue_names}."
        recipients = [(event.organiserId, body)]
        for row in venues + [row for row in arrangements.requests if row.get("status") in SETTLED_REQUESTS]:
            if row.get("reviewedBy"):
                recipients.append((row["reviewedBy"], staff_body))
        messages: dict[str, str] = {}
        for user_id, message in recipients:
            messages.setdefault(user_id, message)
        users = self._directory(authorization)
        for user_id, message in messages.items():
            recipient = self._recipient(users, user_id, event)
            if recipient is not None:
                send_notification(recipient["email"], title, message, authorization)
            record_notification(user_id, event.eventId, "event.confirmed", title, message, authorization)

    def mark_equipment_not_required(
        self,
        event_id: str,
        equipment_id: str,
        data: EquipmentNotRequired,
        coordinator_id: str,
        authorization: str | None = None,
    ) -> EventOut:
        """SPM-72 AC1: the assigned coordinator records that an equipment line is
        not needed after all, with a reason, while the event is in planning."""
        return self._set_equipment_requirement(event_id, equipment_id, coordinator_id, data.reason, authorization)

    def mark_equipment_required(
        self, event_id: str, equipment_id: str, coordinator_id: str, authorization: str | None = None
    ) -> EventOut:
        """Undo: the equipment line is needed again."""
        return self._set_equipment_requirement(event_id, equipment_id, coordinator_id, None, authorization)

    def _set_equipment_requirement(
        self, event_id: str, equipment_id: str, coordinator_id: str, reason: str | None, authorization: str | None
    ) -> EventOut:
        event = self._require_event(event_id)
        _require_assigned_coordinator(event, coordinator_id, "change its equipment needs")
        if event.status not in SAFETY_SUBMITTABLE_STATUSES:
            raise conflict(f"Equipment needs can be changed while the event is in planning (this one is {event.status})")
        lines = [dict(line) for line in event.equipmentLines or []]
        line = self._require(
            next((row for row in lines if row["equipmentId"] == equipment_id), None),
            f"This event has no equipment line for {equipment_id}",
        )
        before = f"not required: {line['notRequiredReason']}" if line.get("notRequired") else "required"
        now = datetime.utcnow()
        for key in ("notRequired", "notRequiredReason", "notRequiredBy", "notRequiredAt"):
            line.pop(key, None)
        if reason is not None:
            line.update(notRequired=True, notRequiredReason=reason, notRequiredBy=coordinator_id, notRequiredAt=now.isoformat())
        after = f"not required: {reason}" if reason is not None else "required"
        if after != before:
            self.field_change_dao.add(
                EventFieldChange(
                    changeId=str(uuid4()),
                    eventId=event.eventId,
                    field=f"equipmentLine:{equipment_id}",
                    oldValue=before,
                    newValue=after,
                    changedBy=coordinator_id,
                    createdAt=now,
                )
            )
            event.equipmentLines = lines
            event.updatedAt = now
            self.db.commit()
            self.db.refresh(event)
        return _to_out(event, authorization)
