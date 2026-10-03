from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EventClarificationReply(Base):
    """SPM-68 AC3: one reply in a clarification thread, with its author, the
    role they wrote as, and when."""

    __tablename__ = "event_clarification_replies"

    replyId: Mapped[str] = mapped_column("reply_id", String(64), primary_key=True)
    reviewId: Mapped[str] = mapped_column("review_id", String(64), ForeignKey("event_reviews.review_id"))
    authorId: Mapped[str] = mapped_column("author_id", String(64))
    authorRole: Mapped[str] = mapped_column("author_role", String(32))
    message: Mapped[str] = mapped_column(Text)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    clarification: Mapped["EventReview"] = relationship("EventReview", back_populates="replies")
