from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.event import Event
from app.orchestration.clients import registration_count
from app.schemas.event import EventCreate, EventOut
from shared.exceptions.http import not_found


def _to_out(row: Event) -> EventOut:
    return EventOut(
        eventId=row.eventId,
        eventName=row.eventName,
        status=row.status,
        registrationEnabled=row.registrationEnabled,
        registrationOpensAt=row.registrationOpensAt,
        registrationClosesAt=row.registrationClosesAt,
        capacity=row.capacity,
        registeredCount=registration_count(row.eventId),
    )


def list_events(db: Session) -> list[EventOut]:
    return [_to_out(row) for row in db.query(Event).all()]


def get_event(db: Session, event_id: str) -> EventOut:
    row = db.query(Event).filter(Event.eventId == event_id).first()
    if not row:
        raise not_found("Event not found")
    return _to_out(row)


def create_event(
    db: Session, data: EventCreate, organiser_id: str, organisation_id: str | None
) -> EventOut:
    """Create an event request.

    New events start at "created". Saving-as-draft and submitting for
    coordinator review are separate transitions to be built later — those are
    what will stamp submitted_at and write event_status_history rows.
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
        status="created",
        submittedAt=None,
        createdAt=now,
        updatedAt=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)
