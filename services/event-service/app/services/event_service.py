import logging
import time
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_change_request_dao import EventChangeRequestDAO
from app.dao.event_dao import EventDAO
from app.dao.event_field_change_dao import EventFieldChangeDAO
from app.dao.event_review_dao import EventReviewDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.models.event import Event
from app.models.event_assignment import EventAssignment
from app.models.event_change_request import EventChangeRequest
from app.models.event_clarification_reply import EventClarificationReply
from app.models.event_field_change import EventFieldChange
from app.models.event_review import EventReview
from app.models.event_status_history import EventStatusHistory
from app.core.config import settings
from app.orchestration.clients import (
    affected_arrangements,
    booked_venue_capacities,
    current_registration_count,
    flag_arrangements,
    list_users,
    organisation_names,
    record_notification,
    registered_attendees,
    registration_count,
    send_notification,
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
    CoordinatorCandidateOut,
    EventActivityOut,
    EventApprovalOut,
    EventAssignmentCreate,
    EventAssignmentOut,
    EventCoordinatorOut,
    EventCreate,
    EventDecisionOut,
    EventDraftUpsert,
    EventInternalNotesOut,
    EventOut,
    EventUpdate,
    EventUpdateOut,
    RegistrationAccessOut,
    RegistrationSettingsOut,
    RegistrationSettingsUpdate,
    SignificantFieldsOut,
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
STAFF_ROLES = ("coordinator", "venue", "techsupport")

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
REGISTRATION_SETUP_STATUSES = ("approved", "planning", "preparing", "prepared", "confirmed", RECONSIDERING)
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


def _date_near(proposed_start: datetime | None) -> bool:
    if proposed_start is None:
        return False
    return (proposed_start - datetime.utcnow()).days <= settings.event_proposed_date_near_days


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
    ):
        super().__init__(db)
        self.event_dao = event_dao
        self.assignment_dao = assignment_dao
        self.history_dao = history_dao
        self.field_change_dao = field_change_dao or EventFieldChangeDAO(db)
        self.review_dao = review_dao or EventReviewDAO(db)
        self.change_request_dao = change_request_dao or EventChangeRequestDAO(db)

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
        """Only events that have been confirmed.

        NOTE: no transition in this service currently sets status to
        "confirmed" - create_event() only ever sets "created". This will return
        an empty list until an approval workflow exists that writes that status.
        """
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
            layoutPreference=None,
            registrationEnabled=False,
            registrationOpensAt=None,
            registrationClosesAt=None,
            capacity=0,
            status="draft",
            submittedAt=None,
            createdAt=now,
            updatedAt=now,
        )
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
        event.updatedAt = datetime.utcnow()
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
        """Every event the caller organises, at any stage, other than one they discarded."""
        rows = self.event_dao.list_by_organiser_excluding_statuses(organiser_id, ["discarded"])
        return _to_out_list(rows, authorization, "list_my_events")

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
                if affected or event.status == "confirmed":
                    raise self._confirmation_required(event, significant, affected)

        now = datetime.utcnow()
        if significant and event.status == "confirmed":
            self._record_status_change(event, RECONSIDERING, changed_by, summary, now)
            event.status = RECONSIDERING
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
        else:
            message = f"Changing {labels} means this event will no longer read as confirmed. Confirm to save the change."
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": message,
                "requiresConfirmation": True,
                "significantFields": significant,
                "arrangements": affected,
                "statusChange": (
                    {"from": event.status, "to": RECONSIDERING} if event.status == "confirmed" else None
                ),
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
        return _to_out(event, authorization)
