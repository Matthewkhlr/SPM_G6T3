from datetime import datetime, timedelta

from app.dao.venue_activity_log_dao import VenueActivityLogDAO
from app.dao.venue_booking_dao import VenueBookingDAO
from app.dao.venue_dao import VenueDAO
from app.dao.venue_unavailability_dao import VenueUnavailabilityDAO
from app.schemas.venue import Layout, OperatingHours, VenueBookingCreate, VenueCreate
from app.services.venue_service import VenueService
from shared.testing.cases import ServiceTestCase

CALLER = {"userId": "u-venue", "userName": "Carol", "role": "venue"}
COORDINATOR = {"userId": "u-coord", "userName": "Ben", "role": "coordinator"}
START = datetime.utcnow() + timedelta(days=10)
END = START + timedelta(hours=8)


def venue_create(**overrides):
    data = dict(
        code="MH-A",
        name="Marina Hall A",
        location="HarbourFront",
        address="1 HarbourFront Walk",
        floor="2",
        description="Main hall",
        facilities=["PA"],
        accessibility=["Ramp"],
        layouts=[Layout(name="Theatre", capacity=100), Layout(name="Classroom", capacity=40)],
        operatingHours=[OperatingHours(day="Mon", opens="08:00", closes="18:00")],
        turnaroundMinutes=60,
    )
    data.update(overrides)
    return VenueCreate(**data)


def booking_create(venue_id, **overrides):
    data = dict(
        venueId=venue_id,
        eventId="e1",
        startsAt=START,
        endsAt=END,
        setupStartsAt=START - timedelta(hours=1),
        teardownEndsAt=END + timedelta(hours=1),
        requirementsSnapshot="Theatre layout",
    )
    data.update(overrides)
    return VenueBookingCreate(**data)


class VenueCase(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.service = VenueService(
            self.db,
            VenueDAO(self.db),
            VenueActivityLogDAO(self.db),
            VenueBookingDAO(self.db),
            VenueUnavailabilityDAO(self.db),
        )
