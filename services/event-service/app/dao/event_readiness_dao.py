from app.models.event_readiness import EventReadinessItem
from shared.dao.base import BaseDAO


class EventReadinessDAO(BaseDAO):
    def list_for_event(self, event_id: str) -> list[EventReadinessItem]:
        return (
            self.db.query(EventReadinessItem)
            .filter(EventReadinessItem.eventId == event_id)
            .order_by(EventReadinessItem.assignedAt, EventReadinessItem.itemId)
            .all()
        )

    def get(self, item_id: str) -> EventReadinessItem | None:
        return self.db.query(EventReadinessItem).filter(EventReadinessItem.itemId == item_id).one_or_none()
