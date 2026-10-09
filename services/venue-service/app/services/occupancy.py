"""SPM-64: the one rule for whether a venue is free for a period.

A booking's occupied window is its event start minus the venue's setup time
through its event end plus the venue's turnaround time (AC2, Week 7 customer
change 1). A period conflicts with a confirmed booking or an unavailability
period whose window overlaps its own; windows that only touch do not (AC6).
A pending request never blocks anyone (SPM-63 AC6); it is reported so callers
can warn about it.

Search (SPM-61), suitability (SPM-62) and booking approval all call
`VenueService.commitments`, which applies this rule. Venue blocking (SPM-9),
rescheduling (SPM-87) and re-verification (SPM-86) are to call it too when they
are built.

SPM-116: an active tentative hold on another pending request reserves the venue
like a confirmed booking (AC2). A hold stops counting the moment its expiry time
passes, or when it ends early (AC3, AC4); it never makes the request a
confirmed booking. Pending requests without an active hold still only warn.

SPM-112 holds every availability and conflict check to this one window, always
worked out from the venue's current setup and turnaround times, and booking
replies report it the same way.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.models.venue_booking import VenueBooking
from app.models.venue_unavailability import VenueUnavailability


def occupied_window(
    starts_at: datetime, ends_at: datetime, setup_minutes: int, turnaround_minutes: int
) -> tuple[datetime, datetime]:
    """AC2: e.g. 10:00 to 12:00 with 30 minutes setup and 45 minutes turnaround is 09:30 to 12:45."""
    return starts_at - timedelta(minutes=setup_minutes), ends_at + timedelta(minutes=turnaround_minutes)


def reach(setup_minutes: int, turnaround_minutes: int) -> timedelta:
    """Two bookings on one venue share its setup and turnaround, so their windows
    overlap exactly when their event times come closer than setup plus turnaround."""
    return timedelta(minutes=setup_minutes + turnaround_minutes)


def hold_state(booking: VenueBooking, now: datetime) -> str | None:
    """SPM-116: None when the request was never held; "active" while the hold
    reserves the venue; "expired" once its expiry has passed (AC3, AC4); else how
    it ended: "released", "approved", "rejected", "withdrawn" or "cancelled"."""
    if booking.holdExpiresAt is None:
        return None
    if booking.holdEndedAt is not None:
        return booking.holdEndReason
    if booking.holdExpiresAt <= now:
        return "expired"
    return "active"


@dataclass
class Commitments:
    """What already holds a venue during a period."""

    confirmed: list[VenueBooking] = field(default_factory=list)
    pending: list[VenueBooking] = field(default_factory=list)
    unavailability: list[VenueUnavailability] = field(default_factory=list)
    held: list[VenueBooking] = field(default_factory=list)

    @property
    def conflicts(self) -> bool:
        """AC3 and AC4: a confirmed booking or an unavailability period means the
        venue is taken, and so does an active tentative hold (SPM-116 AC2)."""
        return bool(self.confirmed or self.unavailability or self.held)
