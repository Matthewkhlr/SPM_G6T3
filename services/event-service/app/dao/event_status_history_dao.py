from sqlalchemy.orm import Session

from app.models.event_status_history import EventStatusHistory


class EventStatusHistoryDAO:
    def __init__(self, db: Session):
        self.db = db

    def add(self, row: EventStatusHistory) -> None:
        self.db.add(row)

    def list_by_event(self, event_id: str) -> list[EventStatusHistory]:
        return (
            self.db.query(EventStatusHistory)
            .filter(EventStatusHistory.eventId == event_id)
            .order_by(EventStatusHistory.createdAt.asc())
            .all()
        )
