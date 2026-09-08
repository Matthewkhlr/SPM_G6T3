from pydantic import BaseModel


class EquipmentOut(BaseModel):
    equipmentId: str
    name: str
    category: str
    status: str
    notes: str
