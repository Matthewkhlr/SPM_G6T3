from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.event_assignment import EventAssignment
from app.models.event_status_history import EventStatusHistory
from app.orchestration.clients import registration_count
from app.schemas.event import EventAssignmentCreate, EventAssignmentOut, EventCreate, EventOut
from shared.exceptions.http import conflict, not_found

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
        proposedStartAt=row.proposedStartAt,
        proposedEndAt=row.proposedEndAt,
        registrationEnabled=row.registrationEnabled,
        registrationOpensAt=row.registrationOpensAt,
        registrationClosesAt=row.registrationClosesAt,
        capacity=row.capacity,
        registeredCount=registration_count(row.eventId),
    )


def list_events(db: Session) -> list[EventOut]:
    return [_to_out(row) for row in db.query(Event).all()]

def list_all_events(db: Session) -> list[EventOut]:
    """Every event except rejected ones."""
    rows = (
        db.query(Event)
        .filter(Event.status != "rejected")
        .order_by(Event.proposedStartAt.asc())
        .all()
    )
    return [_to_out(row) for row in rows]


def list_confirmed_events(db: Session) -> list[EventOut]:
    """Only events that have been confirmed.

    NOTE: no transition in this service currently sets status to
    "confirmed" - create_event() only ever sets "created". This will return
    an empty list until an approval workflow exists that writes that status.
    """
    rows = (
        db.query(Event)
        .filter(Event.status == "confirmed")
        .order_by(Event.proposedStartAt.asc())
        .all()
    )
    return [_to_out(row) for row in rows]


def list_upcoming_events(db: Session) -> list[EventOut]:
    now = datetime.utcnow()

    rows = (
        db.query(Event)
        .filter(Event.proposedEndAt >= now)
        .filter(Event.status.notin_(["rejected", "cancelled", "completed"]))
        .order_by(Event.proposedStartAt.asc())
        .all()
    )

    return [_to_out(row) for row in rows]

def get_event(db: Session, event_id: str) -> EventOut:
    row = db.query(Event).filter(Event.eventId == event_id).first()
    if not row:
        raise not_found("Event not found")
    return _to_out(row)


def create_event(
    db: Session, data: EventCreate, organiser_id: str, organisation_id: str | None
) -> EventOut:
    """Create an event request.

    There is no separate draft-save flow yet, so a created event request is
    immediately "submitted" for coordinator review.
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
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


def assign_coordinator(
    db: Session, event_id: str, data: EventAssignmentCreate, assigned_by: str
) -> EventAssignmentOut:
    event = db.query(Event).filter(Event.eventId == event_id).first()
    if not event:
        raise not_found("Event not found")
    now = datetime.utcnow()
    row = EventAssignment(
        assignmentId=str(uuid4()),
        eventId=event_id,
        coordinatorId=data.coordinatorId,
        assignedBy=assigned_by,
        assignedAt=now,
    )
    db.add(row)
    event.coordinatorId = data.coordinatorId
    event.updatedAt = now
    db.commit()
    db.refresh(row)
    return EventAssignmentOut(
        assignmentId=row.assignmentId,
        eventId=row.eventId,
        coordinatorId=row.coordinatorId,
        assignedBy=row.assignedBy,
        assignedAt=row.assignedAt,
    )


def _record_status_change(db: Session, event: Event, to_status: str, changed_by: str, note: str = "") -> None:
    db.add(
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


def _decide_event(db: Session, event_id: str, coordinator_id: str, new_status: str, reason: str) -> EventOut:
    event = db.query(Event).filter(Event.eventId == event_id).first()
    if not event:
        raise not_found("Event not found")
    if event.status != "submitted":
        raise conflict(f"Event is already {event.status}")
    _record_status_change(db, event, new_status, coordinator_id, reason)
    event.status = new_status
    event.updatedAt = datetime.utcnow()
    db.commit()
    db.refresh(event)
    return _to_out(event)


def approve_event(db: Session, event_id: str, coordinator_id: str) -> EventOut:
    return _decide_event(db, event_id, coordinator_id, "approved", "")


def reject_event(db: Session, event_id: str, coordinator_id: str, reason: str = "") -> EventOut:
    return _decide_event(db, event_id, coordinator_id, "rejected", reason)