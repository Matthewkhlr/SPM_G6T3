from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VenueInfo(Base):
    __tablename__ = "venue_info"

    venueId: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255))
    capacity: Mapped[int] = mapped_column(Integer)
    facilities: Mapped[str] = mapped_column(Text)
    accessibility: Mapped[str] = mapped_column(Text)
    layouts: Mapped[str] = mapped_column(Text)
    operatingHours: Mapped[str] = mapped_column(String(255))
    turnaroundMinutes: Mapped[int] = mapped_column(Integer)
