from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EventChange(Base):
    __tablename__ = "event_change"

    changeId: Mapped[str] = mapped_column(String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)
    changedBy: Mapped[str] = mapped_column(String(64))
    createdAt: Mapped[datetime] = mapped_column(DateTime)
