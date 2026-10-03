from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EquipmentActivityLog(Base):
    __tablename__ = "equipment_activity_log"

    logId: Mapped[str] = mapped_column("log_id", String(64), primary_key=True)
    equipmentId: Mapped[str] = mapped_column(
        "equipment_id", String(64), ForeignKey("equipment_info.equipment_id")
    )
    action: Mapped[str] = mapped_column(String(32))
    changedBy: Mapped[str] = mapped_column("changed_by", String(64))
    changedByName: Mapped[str] = mapped_column("changed_by_name", String(255), default="")
    changedByRole: Mapped[str] = mapped_column("changed_by_role", String(64), default="")
    changes: Mapped[dict] = mapped_column(JSON, default=dict)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)
