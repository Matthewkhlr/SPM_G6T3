from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EquipmentInfo(Base):
    __tablename__ = "equipment_info"

    equipmentId: Mapped[str] = mapped_column("equipment_id", String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    totalQuantity: Mapped[int] = mapped_column("total_quantity", Integer, default=0)

    units: Mapped[list["EquipmentUnit"]] = relationship("EquipmentUnit", back_populates="equipment")
    requests: Mapped[list["EquipmentRequest"]] = relationship("EquipmentRequest", back_populates="equipment")
    reservations: Mapped[list["EquipmentReservation"]] = relationship("EquipmentReservation", back_populates="equipment")
