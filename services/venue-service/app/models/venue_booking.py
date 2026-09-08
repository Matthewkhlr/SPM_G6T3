from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VenueBooking(Base):
    __tablename__ = "venue_booking"

    bookingId: Mapped[str] = mapped_column(String(64), primary_key=True)
    venueId: Mapped[str] = mapped_column(String(64))
    eventId: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requestedBy: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    startsAt: Mapped[datetime] = mapped_column(DateTime)
    endsAt: Mapped[datetime] = mapped_column(DateTime)
