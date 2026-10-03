from app.models.event_assignment import EventAssignment
from shared.dao.base import BaseDAO


class EventAssignmentDAO(BaseDAO):
    def list_by_event(self, event_id: str) -> list[EventAssignment]:
        return (
            self.db.query(EventAssignment)
            .filter(EventAssignment.eventId == event_id)
            .order_by(EventAssignment.assignedAt.asc())
            .all()
        )
