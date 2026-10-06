from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EventReadinessItem(Base):
    """SPM-5: a coordinator follow-up line for one part of an event."""

    __tablename__ = "event_readiness_items"

    itemId: Mapped[str] = mapped_column("item_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64), index=True)
    category: Mapped[str] = mapped_column(String(80))
    handlerId: Mapped[str] = mapped_column("handler_id", String(64), default="")
    handlerName: Mapped[str] = mapped_column("handler_name", String(255), default="")
    handlerEmail: Mapped[str] = mapped_column("handler_email", String(255), default="")
    handlerPhone: Mapped[str] = mapped_column("handler_phone", String(64), default="")
    status: Mapped[str] = mapped_column(String(40), default="outstanding")
    note: Mapped[str] = mapped_column(Text, default="")
    dueAt: Mapped[datetime | None] = mapped_column("due_at", DateTime, nullable=True)
    assignedAt: Mapped[datetime] = mapped_column("assigned_at", DateTime, default=datetime.utcnow)
    attachments: Mapped[list] = mapped_column(JSON, default=list)
