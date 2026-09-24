from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_dao import EventDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.models.event import Event
from app.models.event_assignment import EventAssignment
from app.models.event_status_history import EventStatusHistory
from app.orchestration.clients import registration_count
from app.schemas.event import (
    EventAssignmentCreate,
    EventAssignmentOut,
    EventCreate,
    EventDraftUpsert,
    EventOut,
)
from shared.exceptions.http import conflict, forbidden, not_found

# Full intended event lifecycle. The status column is a free VARCHAR(32) with
# no DB-level enum, so this is documentation for future transitions, not an
# enforced constraint. Only submitted -> approved/rejected is wired up today.
EVENT_STATUSES = (
    "draft",
    "submitted",
    "approved",
    "rejected",
    "preparing",
    "prepared",
    "confirmed",
    "completed",
)


def _to_out(row: Event) -> EventOut:
    return EventOut(
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
        equipmentRequirements=row.equipmentRequirements,
        registrationEnabled=row.registrationEnabled,
        registrationOpensAt=row.registrationOpensAt,
        registrationClosesAt=row.registrationClosesAt,
        capacity=row.capacity,
        registeredCount=registration_count(row.eventId),
    )


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
    ):
        self.db = db
        self.event_dao = event_dao
        self.assignment_dao = assignment_dao
        self.history_dao = history_dao

    def _require_event(self, event_id: str) -> Event:
        row = self.event_dao.get_by_id(event_id)
        if not row:
            raise not_found("Event not found")
        return row

    def list_events(self) -> list[EventOut]:
        """Every event except drafts — a draft is only visible to its own organiser."""
        return [_to_out(row) for row in self.event_dao.list_excluding_draft()]

    def list_all_events(self) -> list[EventOut]:
        """Every event except rejected ones and drafts."""
        return [_to_out(row) for row in self.event_dao.list_excluding_statuses(["rejected", "draft"])]

    def list_confirmed_events(self) -> list[EventOut]:
        """Only events that have been confirmed.

        NOTE: no transition in this service currently sets status to
        "confirmed" - create_event() only ever sets "created". This will return
        an empty list until an approval workflow exists that writes that status.
        """
        return [_to_out(row) for row in self.event_dao.list_by_status("confirmed")]

    def list_upcoming_events(self) -> list[EventOut]:
        now = datetime.utcnow()
        statuses = ["rejected", "cancelled", "completed", "draft"]
        return [_to_out(row) for row in self.event_dao.list_upcoming_excluding_statuses(now, statuses)]

    def get_event(self, event_id: str) -> EventOut:
        return _to_out(self._require_event(event_id))

    def create_event(
        self, data: EventCreate, organiser_id: str, organisation_id: str | None
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
        return _to_out(row)

    def create_draft(
        self, data: EventDraftUpsert, organiser_id: str, organisation_id: str | None
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
        return _to_out(row)

    def _get_own_draft(self, event_id: str, organiser_id: str) -> Event:
        event = self._require_event(event_id)
        if event.organiserId != organiser_id:
            raise forbidden("You do not have permission to edit this event")
        if event.status != "draft":
            raise conflict(f"Event is already {event.status}")
        return event

    def update_draft(self, event_id: str, data: EventDraftUpsert, organiser_id: str) -> EventOut:
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
        return _to_out(event)

    def submit_draft(self, event_id: str, data: EventCreate, organiser_id: str) -> EventOut:
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
        return _to_out(event)

    def list_my_drafts(self, organiser_id: str) -> list[EventOut]:
        return [_to_out(row) for row in self.event_dao.list_drafts_by_organiser(organiser_id)]

    def assign_coordinator(
        self, event_id: str, data: EventAssignmentCreate, assigned_by: str
    ) -> EventAssignmentOut:
        event = self._require_event(event_id)
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
        event.updatedAt = now
        self.db.commit()
        self.db.refresh(row)
        return EventAssignmentOut(
            assignmentId=row.assignmentId,
            eventId=row.eventId,
            coordinatorId=row.coordinatorId,
            assignedBy=row.assignedBy,
            assignedAt=row.assignedAt,
        )

    def _record_status_change(self, event: Event, to_status: str, changed_by: str, note: str = "") -> None:
        self.history_dao.add(
            EventStatusHistory(
                historyId=str(uuid4()),
                eventId=event.eventId,
                fromStatus=event.status,
                toStatus=to_status,
                changedBy=changed_by,
                note=note,
                createdAt=datetime.utcnow(),
            )
        )

    def _decide_event(self, event_id: str, coordinator_id: str, new_status: str, reason: str) -> EventOut:
        event = self._require_event(event_id)
        if event.status != "submitted":
            raise conflict(f"Event is already {event.status}")
        self._record_status_change(event, new_status, coordinator_id, reason)
        event.status = new_status
        event.updatedAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(event)
        return _to_out(event)

    def approve_event(self, event_id: str, coordinator_id: str) -> EventOut:
        return self._decide_event(event_id, coordinator_id, "approved", "")

    def reject_event(self, event_id: str, coordinator_id: str, reason: str = "") -> EventOut:
        return self._decide_event(event_id, coordinator_id, "rejected", reason)
