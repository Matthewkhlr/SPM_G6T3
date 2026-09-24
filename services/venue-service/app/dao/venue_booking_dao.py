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

    def add(self, row: VenueBooking) -> None:
        self.db.add(row)
