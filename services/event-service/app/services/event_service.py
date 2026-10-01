import logging
import time
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_dao import EventDAO
from app.dao.event_field_change_dao import EventFieldChangeDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.models.event import Event
from app.models.event_assignment import EventAssignment
from app.models.event_field_change import EventFieldChange
from app.models.event_status_history import EventStatusHistory
from app.core.config import settings
from app.orchestration.clients import (
    affected_arrangements,
    flag_arrangements,
    list_users,
    organisation_names,
    registration_count,
    send_notification,
)
from app.schemas.event import (
    AffectedArrangement,
    CoordinatorCandidateOut,
    EventActivityOut,
    EventAssignmentCreate,
    EventAssignmentOut,
    EventCoordinatorOut,
    EventCreate,
    EventDraftUpsert,
    EventInternalNotesOut,
    EventOut,
    EventUpdate,
    EventUpdateOut,
    SignificantFieldsOut,
)
from shared.exceptions.http import conflict, forbidden, not_found

logger = logging.getLogger("perf.event_service")

# Full intended event lifecycle. The status column is a free VARCHAR(32) with
# no DB-level enum, so this is documentation for future transitions, not an
# enforced constraint. Only submitted -> approved/rejected is wired up today.
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
# Approve / reject apply while the request waits for a decision. Assigning a
# coordinator moves a submitted request to "under review" (SPM-66 AC6), and it
# must still be decidable from there.
DECIDABLE_STATUSES = ("submitted", "under review")
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
}
# Finished events, and drafts that are not yet requests. They cannot be edited
# (SPM-71 AC7) or assigned a coordinator, and do not count toward a
# coordinator's active events (SPM-66 AC2). A draft still belongs to its
# organiser, who edits it through the draft endpoints.
LOCKED_STATUSES = ("completed", "cancelled", "rejected", "draft", "discarded")
# SPM-71 AC6: a confirmed event whose significant details changed no longer
# reads as fully confirmed while its arrangements are re-checked.
RECONSIDERING = "reconsidering"


def _as_text(value) -> str | None:
    """Activity-log values are stored as text; datetimes use ISO 8601."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _differs(old, new) -> bool:
    """None and an empty string both mean "not set", so moving between them is not an edit."""
    return (old if old != "" else None) != (new if new != "" else None)


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


class EventService:
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
    ):
        self.db = db
        self.event_dao = event_dao
        self.assignment_dao = assignment_dao
        self.history_dao = history_dao
        self.field_change_dao = field_change_dao or EventFieldChangeDAO(db)

    def _require_event(self, event_id: str) -> Event:
        row = self.event_dao.get_by_id(event_id)
        if not row:
            raise not_found("Event not found")
        return row

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
            return _to_out(event, authorization, out_type=EventUpdateOut, internalNotes=event.internalNotes or "")

        significant = [field for field in SIGNIFICANT_FIELDS if field in changes]
        flagged: list[dict] = []
        if significant:
            summary = self._change_summary(event, changes, significant)
            if data.confirmSignificantChange:
                # Flag before saving: if the save then failed, the arrangements
                # would be re-checked needlessly, which is safe; the reverse order
                # could leave a changed event with arrangements nobody re-checks.
                flagged = flag_arrangements(event_id, summary, authorization)
            else:
                affected = affected_arrangements(event_id, authorization)
                if affected or event.status == "confirmed":
                    raise self._confirmation_required(event, significant, affected)

        now = datetime.utcnow()
        if significant and event.status == "confirmed":
            self._record_status_change(event, RECONSIDERING, coordinator_id, summary, now)
            event.status = RECONSIDERING
        for field, value in changes.items():
            self.field_change_dao.add(
                EventFieldChange(
                    changeId=str(uuid4()),
                    eventId=event.eventId,
                    field=field,
                    oldValue=_as_text(getattr(event, field)),
                    newValue=_as_text(value),
                    changedBy=coordinator_id,
                    createdAt=now,
                )
            )
            setattr(event, field, value)
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(event)
        return _to_out(
            event,
            authorization,
            out_type=EventUpdateOut,
            internalNotes=event.internalNotes or "",
            flaggedArrangements=[AffectedArrangement(**row) for row in flagged],
        )

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
        role = caller.get("role")
        if role == "organiser":
            own = caller.get("userId") == event.organiserId
            same_org = bool(caller.get("organisationId")) and caller.get("organisationId") == event.organisationId
            if not (own or same_org):
                raise forbidden("You can only see the coordinator for your organisation's events")
        elif role not in STAFF_ROLES:
            raise forbidden("You do not have permission to see this event's coordinator")
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
        self, event_id: str, coordinator_id: str, authorization: str | None = None
    ) -> EventOut:
        return self._decide_event(event_id, coordinator_id, "approved", "", authorization)

    def reject_event(
        self,
        event_id: str,
        coordinator_id: str,
        reason: str = "",
        authorization: str | None = None,
    ) -> EventOut:
        return self._decide_event(event_id, coordinator_id, "rejected", reason, authorization)
