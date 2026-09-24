from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.schemas.venue import VenueBookingCreate, VenueCreate

CALLER = {"userId": "u-venue-1", "userName": "Vera Venue", "role": "venue"}
COORDINATOR_ID = "u-coordinator-1"


def make_venue(**overrides):
    defaults = dict(
        code="MH-A",
        name="Marina Hall A",
        location="HarbourFront Centre",
        address="",
        floor="2",
        description="",
        facilities=[],
        accessibility=[],
        layouts=[{"name": "Theatre", "capacity": 300}],
        operatingHours=[],
        turnaroundMinutes=60,
    )
    defaults.update(overrides)
    return VenueCreate(**defaults)


def book(venue_id, **overrides):
    starts = datetime.utcnow() + timedelta(days=7)
    defaults = dict(
        venueId=venue_id,
        eventId="e-1",
        startsAt=starts,
        endsAt=starts + timedelta(hours=2),
        setupStartsAt=starts - timedelta(hours=1),
        teardownEndsAt=starts + timedelta(hours=3),
        requirementsSnapshot="Theatre layout, PA system.",
    )
    defaults.update(overrides)
    return VenueBookingCreate(**defaults)


def test_create_booking_starts_pending(venue_service):
    venue = venue_service.create_venue(make_venue(), CALLER)

    booking = venue_service.create_booking(book(venue.venueId), COORDINATOR_ID)

    assert booking.status == "pending"
    assert booking.requestedBy == COORDINATOR_ID
    assert booking.reviewedBy is None


def test_approve_booking_moves_to_approved_and_records_the_reviewer(venue_service):
    venue = venue_service.create_venue(make_venue(), CALLER)
    booking = venue_service.create_booking(book(venue.venueId), COORDINATOR_ID)

    approved = venue_service.approve_booking(booking.bookingId, "u-venue-reviewer", "Hall is free that day.")

    assert approved.status == "approved"
    assert approved.reviewedBy == "u-venue-reviewer"
    assert approved.decisionReason == "Hall is free that day."
    assert approved.reviewedAt is not None


def test_reject_booking_moves_to_rejected_and_records_the_reason(venue_service):
    venue = venue_service.create_venue(make_venue(), CALLER)
    booking = venue_service.create_booking(book(venue.venueId), COORDINATOR_ID)

    rejected = venue_service.reject_booking(booking.bookingId, "u-venue-reviewer", "Hall already booked.")

    assert rejected.status == "rejected"
    assert rejected.decisionReason == "Hall already booked."


def test_approving_an_already_decided_booking_conflicts(venue_service):
    venue = venue_service.create_venue(make_venue(), CALLER)
    booking = venue_service.create_booking(book(venue.venueId), COORDINATOR_ID)
    venue_service.approve_booking(booking.bookingId, "u-venue-reviewer", None)

    with pytest.raises(HTTPException) as exc_info:
        venue_service.approve_booking(booking.bookingId, "u-venue-reviewer", None)

    assert exc_info.value.status_code == 409


def test_approve_booking_missing_id_raises_404(venue_service):
    with pytest.raises(HTTPException) as exc_info:
        venue_service.approve_booking("does-not-exist", "u-venue-reviewer", None)

    assert exc_info.value.status_code == 404
