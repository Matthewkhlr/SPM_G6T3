from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Event(Base):
    __tablename__ = "event_info"

    eventId: Mapped[str] = mapped_column(String(64), primary_key=True)
    eventName: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    registrationEnabled: Mapped[bool] = mapped_column(Boolean, default=False)
    registrationOpensAt: Mapped[datetime] = mapped_column(DateTime)
    registrationClosesAt: Mapped[datetime] = mapped_column(DateTime)
    capacity: Mapped[int] = mapped_column(Integer)
