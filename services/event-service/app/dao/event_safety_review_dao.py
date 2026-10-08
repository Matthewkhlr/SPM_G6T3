from app.models.event_safety_review import EventSafetyReview
from shared.dao.base import BaseDAO


class EventSafetyReviewDAO(BaseDAO):
    def list_by_event(self, event_id: str) -> list[EventSafetyReview]:
        """Newest first."""
        return (
            self.db.query(EventSafetyReview)
            .filter(EventSafetyReview.eventId == event_id)
            .order_by(EventSafetyReview.submittedAt.desc())
            .all()
        )

    def pending_for_event(self, event_id: str) -> EventSafetyReview | None:
        return (
            self.db.query(EventSafetyReview)
            .filter(EventSafetyReview.eventId == event_id, EventSafetyReview.status == "pending")
            .first()
        )

    def list_with_status(self, status: str) -> list[EventSafetyReview]:
        """Longest-waiting first."""
        return (
            self.db.query(EventSafetyReview)
            .filter(EventSafetyReview.status == status)
            .order_by(EventSafetyReview.submittedAt.asc())
            .all()
        )
