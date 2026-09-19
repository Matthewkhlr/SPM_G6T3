import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.venue_booking import VenueBooking
from app.models.venue_info import VenueInfo
from app.schemas.venue import VenueBookingCreate, VenueBookingOut, VenueOut
from shared.exceptions.http import conflict, not_found


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    return json.loads(value)


def _to_out(row: VenueInfo) -> VenueOut:
    return VenueOut(
        venueId=row.venueId,
        name=row.name,
        location=row.location,
        capacity=row.capacity,
        facilities=_as_list(row.facilities),
        accessibility=row.accessibility,
        layouts=_as_list(row.layouts),
        operatingHours=row.operatingHours,
        turnaroundMinutes=row.turnaroundMinutes,
    )


def list_venues(db: Session) -> list[VenueOut]:
    return [_to_out(row) for row in db.query(VenueInfo).all()]


def get_venue(db: Session, venue_id: str) -> VenueOut:
    row = db.query(VenueInfo).filter(VenueInfo.venueId == venue_id).first()
    if not row:
        raise not_found("Venue not found")
    return _to_out(row)


def _booking_to_out(row: VenueBooking) -> VenueBookingOut:
    return VenueBookingOut(
        bookingId=row.bookingId,
        venueId=row.venueId,
        eventId=row.eventId,
        requestedBy=row.requestedBy,
        status=row.status,
        startsAt=row.startsAt,
        endsAt=row.endsAt,
        setupStartsAt=row.setupStartsAt,
        teardownEndsAt=row.teardownEndsAt,
        requirementsSnapshot=row.requirementsSnapshot,
        decisionReason=row.decisionReason,
        reviewedBy=row.reviewedBy,
        reviewedAt=row.reviewedAt,
        createdAt=row.createdAt,
    )


def _get_booking(db: Session, booking_id: str) -> VenueBooking:
    row = db.query(VenueBooking).filter(VenueBooking.bookingId == booking_id).first()
    if not row:
        raise not_found("Venue booking not found")
    return row


def create_booking(db: Session, data: VenueBookingCreate, requested_by: str) -> VenueBookingOut:
    row = VenueBooking(
        bookingId=str(uuid4()),
        venueId=data.venueId,
        eventId=data.eventId,
        requestedBy=requested_by,
        status="pending",
        startsAt=data.startsAt,
        endsAt=data.endsAt,
        setupStartsAt=data.setupStartsAt,
        teardownEndsAt=data.teardownEndsAt,
        requirementsSnapshot=data.requirementsSnapshot,
        createdAt=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _booking_to_out(row)


def approve_booking(db: Session, booking_id: str, reviewer_id: str, reason: str | None) -> VenueBookingOut:
    row = _get_booking(db, booking_id)
    if row.status != "pending":
        raise conflict(f"Booking is already {row.status}")
    row.status = "approved"
    row.decisionReason = reason
    row.reviewedBy = reviewer_id
    row.reviewedAt = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _booking_to_out(row)


def reject_booking(db: Session, booking_id: str, reviewer_id: str, reason: str | None) -> VenueBookingOut:
    row = _get_booking(db, booking_id)
    if row.status != "pending":
        raise conflict(f"Booking is already {row.status}")
    row.status = "rejected"
    row.decisionReason = reason
    row.reviewedBy = reviewer_id
    row.reviewedAt = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _booking_to_out(row)
