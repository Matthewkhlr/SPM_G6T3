from app.models.event_safety_handoff import EventSafetyHandoff
from shared.dao.base import BaseDAO


class EventSafetyHandoffDAO(BaseDAO):
    def get(self, event_id: str) -> EventSafetyHandoff | None:
        return self.db.get(EventSafetyHandoff, event_id)

    def delete(self, row: EventSafetyHandoff) -> None:
        self.db.delete(row)
