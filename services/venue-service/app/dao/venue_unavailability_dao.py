from datetime import datetime

from sqlalchemy.orm import Session

from app.models.venue_unavailability import VenueUnavailability


class VenueUnavailabilityDAO:
    def __init__(self, db: Session):
        self.db = db

    def find_overlapping(self, venue_id: str, starts_at: datetime, ends_at: datetime) -> list[VenueUnavailability]:
        return (
            self.db.query(VenueUnavailability)
            .filter(VenueUnavailability.venueId == venue_id)
            .filter(VenueUnavailability.startsAt < ends_at)
            .filter(VenueUnavailability.endsAt > starts_at)
            .order_by(VenueUnavailability.startsAt)
            .all()
        )
