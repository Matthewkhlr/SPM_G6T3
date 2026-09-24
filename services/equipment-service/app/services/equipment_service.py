from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.equipment_activity_log import EquipmentActivityLog
from app.models.equipment_info import EquipmentInfo
from app.models.equipment_request import EquipmentRequest
from app.models.equipment_reservation import EquipmentReservation
from app.models.equipment_unit import EquipmentUnit
from app.schemas.equipment import (
    EquipmentActivityLogOut,
    EquipmentAvailabilityIn,
    EquipmentAvailabilityOut,
    EquipmentCreate,
    EquipmentOut,
    EquipmentQuantityReserve,
    EquipmentRequestCreate,
    EquipmentRequestOut,
    EquipmentReservationOut,
    EquipmentUpdate,
    OutOfServiceCounts,
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


def _equipment_out(db: Session, row: EquipmentInfo) -> EquipmentOut:
    damaged = row.damagedCount or 0
    maintenance = row.maintenanceCount or 0
    retired = row.retiredCount or 0
    return EquipmentOut(
        equipmentId=row.equipmentId,
        code=row.code or row.equipmentId,
        name=row.name,
        category=row.category,
        description=row.description or "",
        notes=row.description or "",
        status=_status_for(db, row.equipmentId),
        totalQuantity=row.totalQuantity or 0,
        homeLocation=row.homeLocation or row.location or "",
        technicalNotes=row.technicalNotes or "",
        outOfService=OutOfServiceCounts(damaged=damaged, maintenance=maintenance, retired=retired),
        serviceableQuantity=(row.totalQuantity or 0) - damaged - maintenance - retired,
    )


def list_equipment(db: Session) -> list[EquipmentOut]:
    rows = db.query(EquipmentInfo).all()
    rows.sort(key=lambda row: (len(row.equipmentId), row.equipmentId))
    return [_equipment_out(db, row) for row in rows]


def get_equipment(db: Session, equipment_id: str) -> EquipmentOut:
    return _equipment_out(db, _get_equipment_row(db, equipment_id))


def _get_equipment_row(db: Session, equipment_id: str) -> EquipmentInfo:
    row = db.query(EquipmentInfo).filter(EquipmentInfo.equipmentId == equipment_id).first()
    if not row:
        raise not_found("Equipment not found")
    return row


def _naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _counts(damaged: int, maintenance: int, retired: int) -> dict:
    return {"damaged": damaged, "maintenance": maintenance, "retired": retired}


def _reject_invalid_counts(total: int, damaged: int, maintenance: int, retired: int) -> None:
    if total < 0 or min(damaged, maintenance, retired) < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Quantities cannot be negative")
    if damaged + maintenance + retired > total:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Out-of-service counts cannot add up to more than the total owned",
        )


def _active_reservations(db: Session, equipment_id: str) -> list[EquipmentReservation]:
    return (
        db.query(EquipmentReservation)
        .filter(EquipmentReservation.equipmentId == equipment_id)
        .filter(EquipmentReservation.status.in_(["active", "reserved"]))
        .all()
    )


def _overlapping_quantity(rows: list[EquipmentReservation], starts_at: datetime, ends_at: datetime) -> int:
    starts_at, ends_at = _naive(starts_at), _naive(ends_at)
    return sum(row.quantity for row in rows if _naive(row.startsAt) < ends_at and _naive(row.endsAt) > starts_at)


def _events_over_serviceable(rows: list[EquipmentReservation], serviceable: int) -> list[str]:
    points = []
    for row in rows:
        points.append((_naive(row.startsAt), 1, row))
        points.append((_naive(row.endsAt), -1, row))
    points.sort(key=lambda point: (point[0], point[1]))
    running = 0
    active: dict[str, EquipmentReservation] = {}
    event_ids: set[str] = set()
    for _moment, delta, row in points:
        if delta > 0:
            running += row.quantity
            active[row.reservationId] = row
        else:
            running -= row.quantity
            active.pop(row.reservationId, None)
        if running > serviceable:
            event_ids.update(item.eventId for item in active.values())
    return sorted(event_ids)


def _log_change(db: Session, equipment_id: str, action: str, caller: dict, changes: dict) -> None:
    if not changes:
        return
    db.add(
        EquipmentActivityLog(
            logId=str(uuid4()),
            equipmentId=equipment_id,
            action=action,
            changedBy=caller.get("userId", ""),
            changedByName=caller.get("userName", ""),
            changedByRole=caller.get("role", ""),
            changes=changes,
            createdAt=datetime.utcnow(),
        )
    )


def create_equipment(db: Session, data: EquipmentCreate, caller: dict) -> EquipmentOut:
    counts = data.outOfService
    _reject_invalid_counts(data.totalQuantity, counts.damaged, counts.maintenance, counts.retired)
    row = EquipmentInfo(
        equipmentId=str(uuid4()),
        code=data.code,
        name=data.name,
        category=data.category,
        description=data.description,
        location=data.homeLocation,
        homeLocation=data.homeLocation,
        technicalNotes=data.technicalNotes,
        totalQuantity=data.totalQuantity,
        damagedCount=counts.damaged,
        maintenanceCount=counts.maintenance,
        retiredCount=counts.retired,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("An equipment record with this code already exists") from exc
    _log_change(db, row.equipmentId, "created", caller, {"totalQuantity": {"old": None, "new": data.totalQuantity}})
    db.commit()
    db.refresh(row)
    return _equipment_out(db, row)


def update_equipment(db: Session, equipment_id: str, data: EquipmentUpdate, caller: dict) -> EquipmentOut:
    row = _get_equipment_row(db, equipment_id)
    total = data.totalQuantity if data.totalQuantity is not None else row.totalQuantity
    damaged = data.outOfService.damaged if data.outOfService is not None else row.damagedCount
    maintenance = data.outOfService.maintenance if data.outOfService is not None else row.maintenanceCount
    retired = data.outOfService.retired if data.outOfService is not None else row.retiredCount
    _reject_invalid_counts(total, damaged, maintenance, retired)
    serviceable = total - damaged - maintenance - retired
    blocked = _events_over_serviceable(_active_reservations(db, equipment_id), serviceable)
    if blocked and not data.acknowledgeReservationImpact:
        names = ", ".join(blocked)
        raise conflict(f"Serviceable quantity would fall below stock reserved for event {names}")

    changes = {}
    if data.totalQuantity is not None and data.totalQuantity != row.totalQuantity:
        changes["totalQuantity"] = {"old": row.totalQuantity, "new": data.totalQuantity}
        row.totalQuantity = data.totalQuantity
    if data.outOfService is not None:
        old_counts = _counts(row.damagedCount, row.maintenanceCount, row.retiredCount)
        new_counts = _counts(damaged, maintenance, retired)
        if old_counts != new_counts:
            changes["outOfService"] = {"old": old_counts, "new": new_counts}
            row.damagedCount = damaged
            row.maintenanceCount = maintenance
            row.retiredCount = retired
    for field, column in (
        ("code", "code"),
        ("name", "name"),
        ("category", "category"),
        ("description", "description"),
        ("technicalNotes", "technicalNotes"),
    ):
        value = getattr(data, field)
        if value is not None and value != getattr(row, column):
            changes[field] = {"old": getattr(row, column), "new": value}
            setattr(row, column, value)
    if data.homeLocation is not None and data.homeLocation != row.homeLocation:
        changes["homeLocation"] = {"old": row.homeLocation, "new": data.homeLocation}
        row.homeLocation = data.homeLocation
        row.location = data.homeLocation
    _log_change(db, equipment_id, "updated", caller, changes)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("An equipment record with this code already exists") from exc
    db.refresh(row)
    return _equipment_out(db, row)


def check_availability(db: Session, data: EquipmentAvailabilityIn) -> EquipmentAvailabilityOut:
    row = _get_equipment_row(db, data.equipmentId)
    viewed = _equipment_out(db, row)
    reserved = _overlapping_quantity(_active_reservations(db, row.equipmentId), data.startsAt, data.endsAt)
    return EquipmentAvailabilityOut(
        equipmentId=row.equipmentId,
        serviceableQuantity=viewed.serviceableQuantity,
        reservedQuantity=reserved,
        availableQuantity=viewed.serviceableQuantity - reserved,
    )


def get_activity_log(db: Session, equipment_id: str) -> list[EquipmentActivityLogOut]:
    _get_equipment_row(db, equipment_id)
    rows = (
        db.query(EquipmentActivityLog)
        .filter(EquipmentActivityLog.equipmentId == equipment_id)
        .order_by(EquipmentActivityLog.createdAt.desc())
        .all()
    )
    return [
        EquipmentActivityLogOut(
            logId=row.logId,
            equipmentId=row.equipmentId,
            action=row.action,
            changedBy=row.changedBy,
            changedByName=row.changedByName,
            changedByRole=row.changedByRole,
            changes=row.changes or {},
            createdAt=row.createdAt,
        )
        for row in rows
    ]


def reserve_quantity(db: Session, data: EquipmentQuantityReserve, caller: dict) -> EquipmentReservationOut:
    _get_equipment_row(db, data.equipmentId)
    starts_at, ends_at = _naive(data.startsAt), _naive(data.endsAt)
    request = EquipmentRequest(
        requestId=str(uuid4()),
        eventId=data.eventId,
        equipmentId=data.equipmentId,
        quantity=data.quantity,
        technicalRequirements="",
        requestedBy=caller.get("userId", ""),
        status="approved",
        startsAt=starts_at,
        endsAt=ends_at,
        reviewedBy=caller.get("userId"),
        reviewNote="Reserved from the catalogue quantity check",
        createdAt=datetime.utcnow(),
    )
    reservation = EquipmentReservation(
        reservationId=str(uuid4()),
        requestId=request.requestId,
        eventId=data.eventId,
        equipmentId=data.equipmentId,
        quantity=data.quantity,
        startsAt=starts_at,
        endsAt=ends_at,
        status="active",
    )
    db.add(request)
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return _reservation_to_out(reservation)


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
