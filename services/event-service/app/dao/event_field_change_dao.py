from sqlalchemy.orm import Session

from app.models.event_field_change import EventFieldChange


class EventFieldChangeDAO:
    def __init__(self, db: Session):
        self.db = db

    def add(self, row: EventFieldChange) -> None:
        self.db.add(row)

    def list_by_event(self, event_id: str) -> list[EventFieldChange]:
        return (
            self.db.query(EventFieldChange)
            .filter(EventFieldChange.eventId == event_id)
            .order_by(EventFieldChange.createdAt.asc())
            .all()
        )
