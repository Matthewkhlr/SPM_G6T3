from datetime import datetime

from sqlalchemy.orm import Session

from app.models.venue_booking import VenueBooking


class VenueBookingDAO:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, booking_id: str) -> VenueBooking | None:
        return self.db.query(VenueBooking).filter(VenueBooking.bookingId == booking_id).first()

    def find_confirmed_upcoming(self, venue_id: str, after: datetime) -> list[VenueBooking]:
        return (
            self.db.query(VenueBooking)
            .filter(VenueBooking.venueId == venue_id)
            .filter(VenueBooking.status == "approved")
            .filter(VenueBooking.startsAt > after)
            .all()
        )

    def find_overlapping(
        self, venue_id: str, starts_at: datetime, ends_at: datetime, exclude_event_id: str
    ) -> list[VenueBooking]:
        """Pending or approved bookings whose setup-to-teardown window overlaps
        [starts_at, ends_at). Back-to-back windows only touch, so they do not
        overlap. The event's own bookings are left out, so re-checking an
        event never reports it as clashing with itself."""
        return (
            self.db.query(VenueBooking)
            .filter(VenueBooking.venueId == venue_id)
            .filter(VenueBooking.status.in_(("approved", "pending")))
            .filter(VenueBooking.eventId != exclude_event_id)
            .filter(VenueBooking.setupStartsAt < ends_at)
            .filter(VenueBooking.teardownEndsAt > starts_at)
            .order_by(VenueBooking.setupStartsAt)
            .all()
        )

    def add(self, row: VenueBooking) -> None:
        self.db.add(row)
