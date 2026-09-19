from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VenueBooking(Base):
    __tablename__ = "venue_bookings"
    __table_args__ = (Index("ix_venue_bookings_venue_window", "venue_id", "starts_at", "ends_at"),)

    bookingId: Mapped[str] = mapped_column("booking_id", String(64), primary_key=True)
    venueId: Mapped[str] = mapped_column("venue_id", String(64), ForeignKey("venues.venue_id"))
    eventId: Mapped[str] = mapped_column("event_id", String(64))
    requestedBy: Mapped[str] = mapped_column("requested_by", String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    startsAt: Mapped[datetime] = mapped_column("starts_at", DateTime)
    endsAt: Mapped[datetime] = mapped_column("ends_at", DateTime)
    setupStartsAt: Mapped[datetime] = mapped_column("setup_starts_at", DateTime)
    teardownEndsAt: Mapped[datetime] = mapped_column("teardown_ends_at", DateTime)
    requirementsSnapshot: Mapped[str] = mapped_column("requirements_snapshot", Text, default="")
    decisionReason: Mapped[str | None] = mapped_column("decision_reason", Text, nullable=True)
    reviewedBy: Mapped[str | None] = mapped_column("reviewed_by", String(64), nullable=True)
    reviewedAt: Mapped[datetime | None] = mapped_column("reviewed_at", DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    venue: Mapped["VenueInfo"] = relationship("VenueInfo", back_populates="bookings")
