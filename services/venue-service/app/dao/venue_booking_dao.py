from datetime import datetime

from app.models.venue_booking import VenueBooking
from app.models.venue_info import VenueInfo
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

    def list_confirmed_by_venue(self, venue_id: str | None = None) -> list[VenueBooking]:
        """SPM-122: approved bookings that still have their venue record, by venue
        name and then by start, so each venue's bookings sit together in time order."""
        query = (
            self.db.query(VenueBooking)
            .join(VenueBooking.venue)
            .filter(VenueBooking.status == "approved")
        )
        if venue_id:
            query = query.filter(VenueBooking.venueId == venue_id)
        return query.order_by(
            VenueInfo.name, VenueBooking.venueId, VenueBooking.startsAt, VenueBooking.bookingId
        ).all()

    def find_event_times_overlapping(
        self,
        venue_id: str,
        starts_at: datetime,
        ends_at: datetime,
        exclude_event_id: str | None = None,
        lock: bool = False,
    ) -> list[VenueBooking]:
        """Pending or approved bookings on the venue whose event times overlap
        [starts_at, ends_at), earliest first. Touching times do not overlap.
        The searching event's own bookings can be left out.
        `lock` reads the latest committed rows and locks them, for approvals
        (SPM-64 AC7)."""
        query = (
            self.db.query(VenueBooking)
            .filter(VenueBooking.venueId == venue_id)
            .filter(VenueBooking.status.in_(("approved", "pending")))
            .filter(VenueBooking.startsAt < ends_at)
            .filter(VenueBooking.endsAt > starts_at)
        )
        if exclude_event_id:
            query = query.filter(VenueBooking.eventId != exclude_event_id)
        if lock:
            query = query.with_for_update()
        return query.order_by(VenueBooking.startsAt, VenueBooking.bookingId).all()

    def find_live_for_event_venue(self, event_id: str, venue_id: str) -> VenueBooking | None:
        """A pending or approved booking of this venue for this event.

        Withdrawn, rejected, and cancelled rows do not count, so the event can
        request the same venue again after one of those.
        """
        return (
            self.db.query(VenueBooking)
            .filter(VenueBooking.eventId == event_id)
            .filter(VenueBooking.venueId == venue_id)
            .filter(VenueBooking.status.in_(("pending", "approved")))
            .first()
        )

    def list_open_for_event(self, event_id: str) -> list[VenueBooking]:
        """Pending requests and approved bookings still holding a venue."""
        return (
            self.db.query(VenueBooking)
            .filter(VenueBooking.eventId == event_id)
            .filter(VenueBooking.status.in_(("pending", "approved")))
            .order_by(VenueBooking.createdAt, VenueBooking.bookingId)
            .all()
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
