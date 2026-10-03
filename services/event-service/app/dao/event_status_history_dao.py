from app.models.event_status_history import EventStatusHistory
from shared.dao.base import BaseDAO


class EventStatusHistoryDAO(BaseDAO):
    def list_by_event(self, event_id: str) -> list[EventStatusHistory]:
        return (
            self.db.query(EventStatusHistory)
            .filter(EventStatusHistory.eventId == event_id)
            .order_by(EventStatusHistory.createdAt.asc())
            .all()
        )
