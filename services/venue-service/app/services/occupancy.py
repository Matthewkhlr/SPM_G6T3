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
are built, and active tentative holds (SPM-116) are to be added to it.

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


@dataclass
class Commitments:
    """What already holds a venue during a period."""

    confirmed: list[VenueBooking] = field(default_factory=list)
    pending: list[VenueBooking] = field(default_factory=list)
    unavailability: list[VenueUnavailability] = field(default_factory=list)

    @property
    def conflicts(self) -> bool:
        """AC3 and AC4: a confirmed booking or an unavailability period means the venue is taken."""
        return bool(self.confirmed or self.unavailability)
