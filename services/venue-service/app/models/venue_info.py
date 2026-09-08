from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VenueInfo(Base):
    __tablename__ = "venues"

    venueId: Mapped[str] = mapped_column("venue_id", String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255))
    capacity: Mapped[int] = mapped_column(Integer)
    facilities: Mapped[list] = mapped_column(JSON, default=list)
    accessibility: Mapped[str] = mapped_column(Text, default="")
    layouts: Mapped[list] = mapped_column(JSON, default=list)
    operatingHours: Mapped[str] = mapped_column("operating_hours", String(255), default="")
    turnaroundMinutes: Mapped[int] = mapped_column("turnaround_minutes", Integer, default=0)
    isActive: Mapped[bool] = mapped_column("is_active", Boolean, default=True)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    bookings: Mapped[list["VenueBooking"]] = relationship("VenueBooking", back_populates="venue")
    unavailability: Mapped[list["VenueUnavailability"]] = relationship("VenueUnavailability", back_populates="venue")
