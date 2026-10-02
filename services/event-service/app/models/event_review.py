from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EventReview(Base):
    """A coordinator's review action on an event: approve, reject, or
    request_clarification. A clarification (SPM-68) also carries the field it
    concerns, whether it is open or resolved, and the replies under it."""

    __tablename__ = "event_reviews"

    reviewId: Mapped[str] = mapped_column("review_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64), ForeignKey("events.event_id"))
    reviewerId: Mapped[str] = mapped_column("reviewer_id", String(64))
    action: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str] = mapped_column(Text, default="")
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    resolvedBy: Mapped[str | None] = mapped_column("resolved_by", String(64), nullable=True)
    resolvedAt: Mapped[datetime | None] = mapped_column("resolved_at", DateTime, nullable=True)

    event: Mapped["Event"] = relationship("Event", back_populates="reviews")
    replies: Mapped[list["EventClarificationReply"]] = relationship(
        "EventClarificationReply",
        back_populates="clarification",
        order_by="EventClarificationReply.createdAt",
    )
