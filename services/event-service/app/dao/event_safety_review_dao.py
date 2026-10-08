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

    def latest_status_by_event(self, event_ids: list[str]) -> dict[str, str]:
        """Each event's newest review status, in one query."""
        if not event_ids:
            return {}
        rows = (
            self.db.query(EventSafetyReview.eventId, EventSafetyReview.status)
            .filter(EventSafetyReview.eventId.in_(event_ids))
            .order_by(EventSafetyReview.submittedAt.asc())
            .all()
        )
        # Oldest first, so each event keeps its newest status.
        return {event_id: status for event_id, status in rows}

    def list_with_status(self, status: str) -> list[EventSafetyReview]:
        """Longest-waiting first."""
        return (
            self.db.query(EventSafetyReview)
            .filter(EventSafetyReview.status == status)
            .order_by(EventSafetyReview.submittedAt.asc())
            .all()
        )
