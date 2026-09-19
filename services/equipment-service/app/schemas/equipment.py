from datetime import datetime

from pydantic import BaseModel


class EquipmentOut(BaseModel):
    equipmentId: str
    name: str
    category: str
    status: str
    notes: str


class EquipmentRequestCreate(BaseModel):
    eventId: str
    equipmentId: str
    quantity: int = 1
    technicalRequirements: str = ""
    startsAt: datetime
    endsAt: datetime


class EquipmentRequestReview(BaseModel):
    approve: bool
    reviewNote: str = ""


class EquipmentRequestOut(BaseModel):
    requestId: str
    eventId: str
    equipmentId: str
    quantity: int
    technicalRequirements: str
    requestedBy: str
    status: str
    startsAt: datetime
    endsAt: datetime
    reviewedBy: str | None
    reviewNote: str
    createdAt: datetime


class EquipmentReservationOut(BaseModel):
    reservationId: str
    requestId: str
    eventId: str
    equipmentId: str
    quantity: int
    startsAt: datetime
    endsAt: datetime
    status: str
