import json

from sqlalchemy.orm import Session

from app.models.venue_info import VenueInfo
from app.schemas.venue import VenueOut
from shared.exceptions.http import not_found


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
