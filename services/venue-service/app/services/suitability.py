"""SPM-62: one verdict on whether a venue suits an event.

This is the single rule that search (SPM-61), booking requests (SPM-63) and
re-verification after a change (SPM-86) all call, so the three always agree
(AC9). It only judges: the caller loads the venue and the bookings and
unavailability that overlap the event, and passes them in.

Clashes use the shared occupied window (SPM-64): the event's times widened by
the venue's own setup and turnaround time.

All times are UTC, and a venue's opening hours are read as UTC hours.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone

from app.models.venue_booking import VenueBooking
from app.models.venue_unavailability import VenueUnavailability
from app.schemas.venue import EventFacts, SuitabilityReason, SuitabilityRequest, VenueOut
from app.services.occupancy import occupied_window

# Matches datetime.weekday(), and the day keys venues store their hours under.
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class Needs:
    expected_attendance: int
    layout: str | None = None
    facilities: list[str] = field(default_factory=list)
    accessibility: list[str] = field(default_factory=list)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


def _utc(value: datetime | None) -> datetime | None:
    """The database holds naive UTC; a request may send "...Z" or an offset."""
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def needs_for(request: SuitabilityRequest, event: EventFacts) -> Needs:
    """What the event needs: whatever the request states, else the event record."""
    return Needs(
        expected_attendance=(
            request.expectedAttendance if request.expectedAttendance is not None else event.expectedAttendance
        ),
        layout=request.layout if request.layout is not None else event.layoutPreference,
        facilities=request.requiredFacilities,
        accessibility=request.requiredAccessibility,
        starts_at=_utc(request.startsAt or event.proposedStartAt),
        ends_at=_utc(request.endsAt or event.proposedEndAt),
    )


def _schedule_problem(needs: Needs) -> SuitabilityReason | None:
    if needs.starts_at is None or needs.ends_at is None:
        return _warning(
            "schedule",
            "The event has no date and time yet, so opening hours and booking clashes could not be checked.",
        )
    if needs.ends_at <= needs.starts_at:
        return _failure("schedule", "The event's end time must be after its start time.")
    return None


def event_period(needs: Needs) -> tuple[datetime, datetime] | None:
    """The event's own times, or None if they are missing or invalid (so there
    is nothing to clash with)."""
    if _schedule_problem(needs):
        return None
    return needs.starts_at, needs.ends_at


def _failure(check: str, message: str) -> SuitabilityReason:
    return SuitabilityReason(severity="failure", check=check, message=message)


def _warning(check: str, message: str) -> SuitabilityReason:
    return SuitabilityReason(severity="warning", check=check, message=message)


def _clock(moment: datetime) -> str:
    return moment.strftime("%I:%M %p")


def _span(start: datetime, end: datetime) -> str:
    if start.date() == end.date():
        return f"{start:%d %b %Y}, {_clock(start)} to {_clock(end)} UTC"
    return f"{start:%d %b %Y}, {_clock(start)} to {end:%d %b %Y}, {_clock(end)} UTC"


def _hours(value: str) -> timedelta:
    hours, minutes = value.split(":")
    return timedelta(hours=int(hours), minutes=int(minutes))


def _layout_and_capacity(venue: VenueOut, needs: Needs) -> list[SuitabilityReason]:
    capacity, where = venue.capacity, ""
    if needs.layout:
        wanted = needs.layout.strip().casefold()
        match = next((layout for layout in venue.layouts if layout.name.casefold() == wanted), None)
        if match is None:
            offered = ", ".join(layout.name for layout in venue.layouts) or "none"
            return [
                _failure("layout", f"This venue does not offer the {needs.layout} layout. Layouts offered: {offered}.")
            ]
        capacity, where = match.capacity, f" in the {match.name} layout"

    attendance = needs.expected_attendance
    if attendance > capacity:
        return [
            _failure(
                "capacity",
                f"Expected attendance of {attendance} is more than this venue can hold{where} ({capacity} people).",
            )
        ]
    # AC6: above about ninety per cent is a tight fit, flagged but not blocked.
    # Whole numbers only, so 18 of 20 (exactly 90%) is not flagged but 19 is.
    if attendance * 10 > capacity * 9:
        return [
            _warning(
                "capacity",
                f"Expected attendance of {attendance} is above 90% of what this venue can hold{where} "
                f"({capacity} people), so it will be a tight fit.",
            )
        ]
    return []


def _missing(required: list[str], offered: list[str]) -> list[str]:
    have = {item.strip().casefold() for item in offered}
    missing, seen = [], set()
    for item in required:
        key = item.strip().casefold()
        if key and key not in have and key not in seen:
            seen.add(key)
            missing.append(item.strip())
    return missing


def _opening_hours(venue: VenueOut, start: datetime, end: datetime) -> list[SuitabilityReason]:
    """Every calendar day the event touches must fall inside that day's hours."""
    hours = {slot.day: slot for slot in venue.operatingHours}
    reasons = []
    day_start = datetime.combine(start.date(), time.min)
    while day_start < end:
        part_from, part_until = max(start, day_start), min(end, day_start + timedelta(days=1))
        label = f"{day_start:%A %d %b %Y}"
        slot = hours.get(DAY_NAMES[day_start.weekday()])
        if slot is None:
            reasons.append(
                _failure("openingHours", f"This venue is closed on {label}, so the event is outside its opening hours.")
            )
        elif part_from < day_start + _hours(slot.opens) or part_until > day_start + _hours(slot.closes):
            reasons.append(
                _failure(
                    "openingHours",
                    f"On {label} the event runs {_clock(part_from)} to {_clock(part_until)} UTC, outside this "
                    f"venue's opening hours of {slot.opens} to {slot.closes} UTC.",
                )
            )
        day_start += timedelta(days=1)
    return reasons


def _event_label(booking: VenueBooking) -> str:
    """Name the other event in plain words. Requests sent since SPM-63 carry the
    event's name; older bookings only have its id."""
    name = (booking.eventSnapshot or {}).get("eventName")
    return f'"{name}"' if name else f"event {booking.eventId}"


def _moment(value: datetime) -> str:
    return f"{value:%d %b %Y}, {_clock(value)} UTC"


def _clashes(
    venue: VenueOut,
    bookings: list[VenueBooking],
    unavailability: list[VenueUnavailability],
    holds: list[VenueBooking] = (),
) -> list[SuitabilityReason]:
    reasons = []
    for booking in holds:
        # SPM-116 AC2: an active tentative hold reserves the venue, so it is a failure.
        when = _span(*occupied_window(booking.startsAt, booking.endsAt, venue.setupMinutes, venue.turnaroundMinutes))
        reasons.append(
            _failure(
                "hold",
                f"This venue is on a tentative hold for {_event_label(booking)} until "
                f"{_moment(booking.holdExpiresAt)}, at an overlapping time ({when}, including setup and turnaround).",
            )
        )
    for booking in bookings:
        when = _span(*occupied_window(booking.startsAt, booking.endsAt, venue.setupMinutes, venue.turnaroundMinutes))
        if booking.status == "approved":
            reasons.append(
                _failure(
                    "clash",
                    f"This venue already has a confirmed booking for {_event_label(booking)} at an overlapping "
                    f"time ({when}, including setup and turnaround).",
                )
            )
        else:
            reasons.append(
                _warning(
                    "pendingRequest",
                    f"Another booking request for this venue ({_event_label(booking)}) is waiting for a decision "
                    f"at an overlapping time ({when}). You can still go ahead, but Venue Staff can approve only "
                    f"one of them.",
                )
            )
    for period in unavailability:
        why = f" ({period.reason})" if period.reason else ""
        reasons.append(
            _failure("unavailable", f"This venue is unavailable from {_span(period.startsAt, period.endsAt)}{why}.")
        )
    return reasons


def assess(
    venue: VenueOut,
    needs: Needs,
    bookings: list[VenueBooking],
    unavailability: list[VenueUnavailability],
    holds: list[VenueBooking] = (),
) -> tuple[str, list[SuitabilityReason]]:
    """`bookings` are the pending or approved bookings of other events that
    overlap the event's setup-to-teardown window; `unavailability` is the
    unavailability that overlaps it; `holds` are other events' requests under an
    active tentative hold that overlap it (SPM-116)."""
    reasons = []
    if not venue.isActive:
        reasons.append(_failure("retired", "This venue has been retired and can no longer be booked."))
    reasons += _layout_and_capacity(venue, needs)
    for item in _missing(needs.facilities, venue.facilities):
        reasons.append(_failure("facility", f"Required facility not available at this venue: {item}."))
    for item in _missing(needs.accessibility, venue.accessibility):
        reasons.append(
            _failure("accessibility", f"Required accessibility feature not available at this venue: {item}.")
        )

    problem = _schedule_problem(needs)
    if problem:
        reasons.append(problem)
    else:
        reasons += _opening_hours(venue, needs.starts_at, needs.ends_at)
        reasons += _clashes(venue, bookings, unavailability, holds)

    reasons.sort(key=lambda reason: reason.severity != "failure")
    if any(reason.severity == "failure" for reason in reasons):
        return "not suitable", reasons
    if reasons:
        return "suitable with warnings", reasons
    return "suitable", reasons
