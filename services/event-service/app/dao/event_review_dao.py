from sqlalchemy.orm import selectinload

from app.models.event_review import EventReview
from shared.dao.base import BaseDAO


class EventReviewDAO(BaseDAO):
    def latest_with_action(self, event_id: str, actions: list[str]) -> EventReview | None:
        """The event's most recent review whose action is one of `actions`."""
        return (
            self.db.query(EventReview)
            .filter(EventReview.eventId == event_id, EventReview.action.in_(actions))
            .order_by(EventReview.createdAt.desc())
            .first()
        )

    def list_with_replies(self, event_id: str, action: str) -> list[EventReview]:
        """The event's reviews with `action`, oldest first, each with its replies loaded."""
        return (
            self.db.query(EventReview)
            .options(selectinload(EventReview.replies))
            .filter(EventReview.eventId == event_id, EventReview.action == action)
            .order_by(EventReview.createdAt.asc())
            .all()
        )

    def get_with_action(self, event_id: str, review_id: str, action: str) -> EventReview | None:
        return (
            self.db.query(EventReview)
            .filter(EventReview.eventId == event_id, EventReview.reviewId == review_id, EventReview.action == action)
            .first()
        )
