from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Notification(Base):
    __tablename__ = "notifications"

    notificationId: Mapped[str] = mapped_column("notification_id", String(64), primary_key=True)
    userId: Mapped[str] = mapped_column("user_id", String(64), index=True)
    eventId: Mapped[str | None] = mapped_column("event_id", String(64), nullable=True)
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    isRead: Mapped[bool] = mapped_column("is_read", Boolean, default=False)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow, index=True)
