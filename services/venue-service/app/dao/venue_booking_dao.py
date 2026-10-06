from datetime import datetime

from app.models.venue_booking import VenueBooking
from shared.dao.base import BaseDAO


class VenueBookingDAO(BaseDAO):
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

    def find_event_times_overlapping(
        self, venue_id: str, starts_at: datetime, ends_at: datetime, exclude_event_id: str | None
    ) -> list[VenueBooking]:
        """Pending or approved bookings on the venue whose event times overlap
        [starts_at, ends_at). Touching times do not overlap. The searching
        event's own bookings are left out when it is named."""
        query = (
            self.db.query(VenueBooking)
            .filter(VenueBooking.venueId == venue_id)
            .filter(VenueBooking.status.in_(("approved", "pending")))
            .filter(VenueBooking.startsAt < ends_at)
            .filter(VenueBooking.endsAt > starts_at)
        )
        if exclude_event_id:
            query = query.filter(VenueBooking.eventId != exclude_event_id)
        return query.all()

    def find_pending_for_event(self, event_id: str) -> VenueBooking | None:
        return (
            self.db.query(VenueBooking)
            .filter(VenueBooking.eventId == event_id)
            .filter(VenueBooking.status == "pending")
            .first()
        )

    def list(self, status: str | None, event_id: str | None, venue_id: str | None) -> list[VenueBooking]:
        """Oldest first: the customer handles venue requests first come, first served."""
        query = self.db.query(VenueBooking)
        if status:
            query = query.filter(VenueBooking.status == status)
        if event_id:
            query = query.filter(VenueBooking.eventId == event_id)
        if venue_id:
            query = query.filter(VenueBooking.venueId == venue_id)
        return query.order_by(VenueBooking.createdAt, VenueBooking.bookingId).all()
