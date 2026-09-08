from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EquipmentUnit(Base):
    __tablename__ = "equipment_units"

    unitId: Mapped[str] = mapped_column("unit_id", String(64), primary_key=True)
    equipmentId: Mapped[str] = mapped_column(
        "equipment_id", String(64), ForeignKey("equipment_info.equipment_id")
    )
    status: Mapped[str] = mapped_column(String(32), default="available")

    equipment: Mapped["EquipmentInfo"] = relationship("EquipmentInfo", back_populates="units")
