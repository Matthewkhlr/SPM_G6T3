from sqlalchemy.orm import Session

from app.models.event_assignment import EventAssignment


class EventAssignmentDAO:
    def __init__(self, db: Session):
        self.db = db

    def add(self, row: EventAssignment) -> None:
        self.db.add(row)

    def list_by_event(self, event_id: str) -> list[EventAssignment]:
        return (
            self.db.query(EventAssignment)
            .filter(EventAssignment.eventId == event_id)
            .order_by(EventAssignment.assignedAt.asc())
            .all()
        )
