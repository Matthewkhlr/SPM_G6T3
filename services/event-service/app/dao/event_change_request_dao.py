from app.models.event_change_request import EventChangeRequest
from shared.dao.base import BaseDAO


class EventChangeRequestDAO(BaseDAO):
    def list_by_event(self, event_id: str) -> list[EventChangeRequest]:
        """Newest first."""
        return (
            self.db.query(EventChangeRequest)
            .filter(EventChangeRequest.eventId == event_id)
            .order_by(EventChangeRequest.createdAt.desc())
            .all()
        )

    def get_for_event(self, event_id: str, change_request_id: str) -> EventChangeRequest | None:
        return (
            self.db.query(EventChangeRequest)
            .filter(EventChangeRequest.eventId == event_id, EventChangeRequest.changeRequestId == change_request_id)
            .first()
        )

    def has_with_status(self, event_id: str, status: str) -> bool:
        return (
            self.db.query(EventChangeRequest.changeRequestId)
            .filter(EventChangeRequest.eventId == event_id, EventChangeRequest.status == status)
            .first()
            is not None
        )
