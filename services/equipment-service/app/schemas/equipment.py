from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OutOfServiceCounts(BaseModel):
    damaged: int = 0
    maintenance: int = 0
    retired: int = 0


class EquipmentCreate(BaseModel):
    code: str
    name: str
    category: str
    description: str = ""
    totalQuantity: int
    homeLocation: str = ""
    technicalNotes: str = ""
    outOfService: OutOfServiceCounts = Field(default_factory=OutOfServiceCounts)


class EquipmentUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    category: str | None = None
    description: str | None = None
    totalQuantity: int | None = None
    homeLocation: str | None = None
    technicalNotes: str | None = None
    outOfService: OutOfServiceCounts | None = None
    acknowledgeReservationImpact: bool = False


class EquipmentAvailabilityIn(BaseModel):
    equipmentId: str
    startsAt: datetime
    endsAt: datetime


class EquipmentAvailabilityOut(BaseModel):
    equipmentId: str
    availableQuantity: int
    serviceableQuantity: int
    reservedQuantity: int


class EquipmentActivityLogOut(BaseModel):
    logId: str
    equipmentId: str
    action: str
    changedBy: str
    changedByName: str
    changedByRole: str
    changes: dict
    createdAt: datetime


class EquipmentQuantityReserve(BaseModel):
    eventId: str
    equipmentId: str
    quantity: int
    startsAt: datetime
    endsAt: datetime


class EquipmentOut(BaseModel):
    equipmentId: str
    code: str = ""
    name: str
    category: str
    description: str = ""
    status: str = Field(description="Derived from unit rows: `available`, `maintenance`, or `damaged`.")
    notes: str
    totalQuantity: int = 0
    homeLocation: str = ""
    technicalNotes: str = ""
    outOfService: OutOfServiceCounts = Field(default_factory=OutOfServiceCounts)
    serviceableQuantity: int = 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "equipmentId": "eq1",
                "code": "eq1",
                "name": "Projector PX-200",
                "category": "display",
                "description": "Includes HDMI + VGA adapters",
                "status": "available",
                "notes": "Includes HDMI + VGA adapters",
                "totalQuantity": 4,
                "homeLocation": "Marina Hall store",
                "technicalNotes": "Keep a spare lamp in the same store.",
                "outOfService": {"damaged": 0, "maintenance": 0, "retired": 0},
                "serviceableQuantity": 4,
            }
        }
    )


class EquipmentRequestCreate(BaseModel):
    eventId: str
    equipmentId: str
    quantity: int = 1
    technicalRequirements: str = ""
    startsAt: datetime
    endsAt: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "equipmentId": "eq1",
                "quantity": 1,
                "technicalRequirements": "HDMI to the lectern.",
                "startsAt": "2026-10-06T08:00:00",
                "endsAt": "2026-10-06T18:00:00",
            }
        }
    )


class EquipmentRequestReview(BaseModel):
    approve: bool
    reviewNote: str = ""

    model_config = ConfigDict(
        json_schema_extra={"example": {"approve": True, "reviewNote": "Stock is free that day."}}
    )


class EquipmentRequestOut(BaseModel):
    requestId: str
    eventId: str
    equipmentId: str
    quantity: int
    technicalRequirements: str
    requestedBy: str
    status: str = Field(description="`pending`, `approved`, `rejected`, or `reserved`.")
    startsAt: datetime
    endsAt: datetime
    reviewedBy: str | None
    reviewNote: str
    createdAt: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "requestId": "req-1",
                "eventId": "e1",
                "equipmentId": "eq1",
                "quantity": 1,
                "technicalRequirements": "HDMI to the lectern.",
                "requestedBy": "u2",
                "status": "pending",
                "startsAt": "2026-10-06T08:00:00",
                "endsAt": "2026-10-06T18:00:00",
                "reviewedBy": None,
                "reviewNote": "",
                "createdAt": "2026-09-20T10:00:00",
            }
        }
    )


class EquipmentReservationOut(BaseModel):
    reservationId: str
    requestId: str
    eventId: str
    equipmentId: str
    quantity: int
    startsAt: datetime
    endsAt: datetime
    status: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reservationId": "rsv-1",
                "requestId": "req-1",
                "eventId": "e1",
                "equipmentId": "eq1",
                "quantity": 1,
                "startsAt": "2026-10-06T08:00:00",
                "endsAt": "2026-10-06T18:00:00",
                "status": "reserved",
            }
        }
    )
