from sqlalchemy.orm import Session

from app.models.event import Event
from app.orchestration.clients import registration_count
from app.schemas.event import EventOut
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
