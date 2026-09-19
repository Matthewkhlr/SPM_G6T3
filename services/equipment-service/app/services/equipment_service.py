from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.equipment_info import EquipmentInfo
from app.models.equipment_request import EquipmentRequest
from app.models.equipment_reservation import EquipmentReservation
from app.models.equipment_unit import EquipmentUnit
from app.schemas.equipment import (
    EquipmentOut,
    EquipmentRequestCreate,
    EquipmentRequestOut,
    EquipmentReservationOut,
)
from shared.exceptions.http import conflict, not_found


def _status_for(db: Session, equipment_id: str) -> str:
    units = db.query(EquipmentUnit).filter(EquipmentUnit.equipmentId == equipment_id).all()
    if not units:
        return "available"
    if any(unit.status == "maintenance" for unit in units):
        return "maintenance"
    if any(unit.status == "damaged" for unit in units):
        return "damaged"
    return "available"


def list_equipment(db: Session) -> list[EquipmentOut]:
    return [
        EquipmentOut(
            equipmentId=row.equipmentId,
            name=row.name,
            category=row.category,
            notes=row.description,
            status=_status_for(db, row.equipmentId),
        )
        for row in db.query(EquipmentInfo).all()
    ]


def get_equipment(db: Session, equipment_id: str) -> EquipmentOut:
    row = db.query(EquipmentInfo).filter(EquipmentInfo.equipmentId == equipment_id).first()
    if not row:
        raise not_found("Equipment not found")
    return EquipmentOut(
        equipmentId=row.equipmentId,
        name=row.name,
        category=row.category,
        notes=row.description,
        status=_status_for(db, equipment_id),
    )


def _request_to_out(row: EquipmentRequest) -> EquipmentRequestOut:
    return EquipmentRequestOut(
        requestId=row.requestId,
        eventId=row.eventId,
        equipmentId=row.equipmentId,
        quantity=row.quantity,
        technicalRequirements=row.technicalRequirements,
        requestedBy=row.requestedBy,
        status=row.status,
        startsAt=row.startsAt,
        endsAt=row.endsAt,
        reviewedBy=row.reviewedBy,
        reviewNote=row.reviewNote,
        createdAt=row.createdAt,
    )


def _reservation_to_out(row: EquipmentReservation) -> EquipmentReservationOut:
    return EquipmentReservationOut(
        reservationId=row.reservationId,
        requestId=row.requestId,
        eventId=row.eventId,
        equipmentId=row.equipmentId,
        quantity=row.quantity,
        startsAt=row.startsAt,
        endsAt=row.endsAt,
        status=row.status,
    )


def _get_request(db: Session, request_id: str) -> EquipmentRequest:
    row = db.query(EquipmentRequest).filter(EquipmentRequest.requestId == request_id).first()
    if not row:
        raise not_found("Equipment request not found")
    return row


def create_request(db: Session, data: EquipmentRequestCreate, requested_by: str) -> EquipmentRequestOut:
    row = EquipmentRequest(
        requestId=str(uuid4()),
        eventId=data.eventId,
        equipmentId=data.equipmentId,
        quantity=data.quantity,
        technicalRequirements=data.technicalRequirements,
        requestedBy=requested_by,
        status="pending",
        startsAt=data.startsAt,
        endsAt=data.endsAt,
        createdAt=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _request_to_out(row)


def review_request(
    db: Session, request_id: str, reviewer_id: str, approve: bool, review_note: str
) -> EquipmentRequestOut:
    row = _get_request(db, request_id)
    if row.status != "pending":
        raise conflict(f"Request is already {row.status}")
    row.status = "approved" if approve else "rejected"
    row.reviewedBy = reviewer_id
    row.reviewNote = review_note
    db.commit()
    db.refresh(row)
    return _request_to_out(row)


def reserve_request(db: Session, request_id: str) -> EquipmentReservationOut:
    request_row = _get_request(db, request_id)
    if request_row.status != "approved":
        raise conflict("Only approved requests can be reserved")
    existing = (
        db.query(EquipmentReservation)
        .filter(EquipmentReservation.requestId == request_id)
        .first()
    )
    if existing:
        raise conflict("Request is already reserved")
    row = EquipmentReservation(
        reservationId=str(uuid4()),
        requestId=request_row.requestId,
        eventId=request_row.eventId,
        equipmentId=request_row.equipmentId,
        quantity=request_row.quantity,
        startsAt=request_row.startsAt,
        endsAt=request_row.endsAt,
        status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _reservation_to_out(row)
