from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.dao.venue_activity_log_dao import VenueActivityLogDAO
from app.dao.venue_booking_dao import VenueBookingDAO
from app.dao.venue_dao import VenueDAO
from app.schemas.venue import VenueBookingCreate, VenueCreate
from app.services.venue_service import VenueService

CALLER = {"userId": "u-venue-1", "userName": "Vera Venue", "role": "venue"}
COORDINATOR_ID = "u-coordinator-1"


def make_venue(**overrides):
    defaults = dict(
        code="MH-A",
        name="Marina Hall A",
        location="HarbourFront Centre",
        address="1 HarbourFront Walk, Singapore 098585",
        floor="2",
        description="Largest multipurpose hall.",
        facilities=[],
        accessibility=[],
        layouts=[{"name": "Theatre", "capacity": 300}],
        operatingHours=[],
        turnaroundMinutes=60,
    )
    defaults.update(overrides)
    return VenueCreate(**defaults)


def book(venue_id, starts_at, **overrides):
    defaults = dict(
        venueId=venue_id,
        eventId="e-1",
        startsAt=starts_at,
        endsAt=starts_at + timedelta(hours=2),
        setupStartsAt=starts_at - timedelta(hours=1),
        teardownEndsAt=starts_at + timedelta(hours=3),
        requirementsSnapshot="",
    )
    defaults.update(overrides)
    return VenueBookingCreate(**defaults)


# --- AC5: real DAO + real (in-memory) database, matching the rest of the suite ---


def test_retire_succeeds_when_there_are_no_bookings_at_all(venue_service):
    created = venue_service.create_venue(make_venue(), CALLER)

    retired = venue_service.retire_venue(created.venueId, CALLER)

    assert retired.isActive is False


def test_retire_is_blocked_by_an_approved_upcoming_booking(venue_service):
    created = venue_service.create_venue(make_venue(), CALLER)
    future = datetime.utcnow() + timedelta(days=7)
    booking = venue_service.create_booking(book(created.venueId, future, eventId="e-42"), COORDINATOR_ID)
    venue_service.approve_booking(booking.bookingId, "u-venue-reviewer", None)

    with pytest.raises(HTTPException) as exc_info:
        venue_service.retire_venue(created.venueId, CALLER, confirm=False)

    assert exc_info.value.status_code == 409
    assert "e-42" in exc_info.value.detail

    # and it genuinely didn't retire the venue
    assert venue_service.get_venue(created.venueId).isActive is True


def test_retire_succeeds_anyway_when_confirm_is_true(venue_service):
    created = venue_service.create_venue(make_venue(), CALLER)
    future = datetime.utcnow() + timedelta(days=7)
    booking = venue_service.create_booking(book(created.venueId, future, eventId="e-43"), COORDINATOR_ID)
    venue_service.approve_booking(booking.bookingId, "u-venue-reviewer", None)

    retired = venue_service.retire_venue(created.venueId, CALLER, confirm=True)

    assert retired.isActive is False


def test_retire_is_not_blocked_by_a_still_pending_booking(venue_service):
    created = venue_service.create_venue(make_venue(), CALLER)
    future = datetime.utcnow() + timedelta(days=7)
    venue_service.create_booking(book(created.venueId, future), COORDINATOR_ID)  # never approved

    retired = venue_service.retire_venue(created.venueId, CALLER, confirm=False)

    assert retired.isActive is False


def test_retire_is_not_blocked_by_an_approved_booking_that_already_happened(venue_service):
    created = venue_service.create_venue(make_venue(), CALLER)
    past = datetime.utcnow() - timedelta(days=7)
    booking = venue_service.create_booking(book(created.venueId, past), COORDINATOR_ID)
    venue_service.approve_booking(booking.bookingId, "u-venue-reviewer", None)

    retired = venue_service.retire_venue(created.venueId, CALLER, confirm=False)

    assert retired.isActive is False


def test_retire_missing_venue_raises_404(venue_service):
    with pytest.raises(HTTPException) as exc_info:
        venue_service.retire_venue("does-not-exist", CALLER)

    assert exc_info.value.status_code == 404


# --- Same AC5 logic in isolation: DAOs replaced with MagicMock, no database at all.
# Demonstrates that splitting the DAO out actually buys substitutability, not just structure. ---


def test_retire_conflict_logic_in_isolation_with_mocked_daos():
    db = MagicMock()
    venue_dao = MagicMock(spec=VenueDAO)
    log_dao = MagicMock(spec=VenueActivityLogDAO)
    booking_dao = MagicMock(spec=VenueBookingDAO)
    service = VenueService(db, venue_dao, log_dao, booking_dao)

    venue_dao.get_by_id.return_value = SimpleNamespace(venueId="v1", isActive=True)
    booking_dao.find_confirmed_upcoming.return_value = [
        SimpleNamespace(eventId="e-99", startsAt=datetime(2030, 6, 1, 9, 0))
    ]

    with pytest.raises(HTTPException) as exc_info:
        service.retire_venue("v1", CALLER, confirm=False)

    assert exc_info.value.status_code == 409
    assert "e-99" in exc_info.value.detail
    log_dao.log.assert_not_called()
    db.commit.assert_not_called()


def test_retire_success_path_in_isolation_with_mocked_daos():
    db = MagicMock()
    venue_dao = MagicMock(spec=VenueDAO)
    log_dao = MagicMock(spec=VenueActivityLogDAO)
    booking_dao = MagicMock(spec=VenueBookingDAO)
    service = VenueService(db, venue_dao, log_dao, booking_dao)

    venue_row = SimpleNamespace(
        venueId="v1",
        isActive=True,
        code="MH-A",
        name="Hall",
        location="L",
        address="A",
        floor="1",
        description="",
        facilities=[],
        accessibility=[],
        layouts=[{"name": "Theatre", "capacity": 10}],
        operatingHours=[],
        turnaroundMinutes=0,
    )
    venue_dao.get_by_id.return_value = venue_row
    booking_dao.find_confirmed_upcoming.return_value = []

    result = service.retire_venue("v1", CALLER)

    assert venue_row.isActive is False
    assert result.isActive is False
    log_dao.log.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(venue_row)
