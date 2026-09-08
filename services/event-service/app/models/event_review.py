from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EventReview(Base):
    __tablename__ = "event_reviews"

    reviewId: Mapped[str] = mapped_column("review_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64), ForeignKey("events.event_id"))
    reviewerId: Mapped[str] = mapped_column("reviewer_id", String(64))
    action: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str] = mapped_column(Text, default="")
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    event: Mapped["Event"] = relationship("Event", back_populates="reviews")
