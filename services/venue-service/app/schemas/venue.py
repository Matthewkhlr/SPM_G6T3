from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OperatingHours(BaseModel):
    day: str
    opens: str
    closes: str


class Layout(BaseModel):
    # No fixed whitelist here: the customer explicitly said layout names can
    # be "classroom, theatre, boardroom, banquet, exhibition, or another
    # arrangement" and that the team could "suggest your own list" -- so the
    # published list lives as a guided dropdown in the UI (with an "Other"
    # escape hatch), not a hard server-side restriction. A name is still
    # required to be non-empty regardless of which path it came from.
    name: str = Field(min_length=1)
    capacity: int = Field(gt=0)


class VenueOut(BaseModel):
    venueId: str
    code: str
    name: str
    location: str
    address: str
    floor: str
    description: str
    capacity: int
    facilities: list[str]
    accessibility: list[str]
    layouts: list[Layout]
    operatingHours: list[OperatingHours]
    setupMinutes: int
    turnaroundMinutes: int
    isActive: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "venueId": "v1",
                "code": "MH-A",
                "name": "Marina Hall A",
                "location": "HarbourFront Centre",
                "address": "1 HarbourFront Walk, Singapore 098585",
                "floor": "2",
                "description": "ConnectSphere's largest multipurpose hall.",
                "capacity": 300,
                "facilities": ["Projector", "PA system", "Video-conferencing", "Stage"],
                "accessibility": ["Wheelchair accessible", "Accessible restrooms nearby"],
                "layouts": [
                    {"name": "Theatre", "capacity": 300},
                    {"name": "Classroom", "capacity": 180},
                    {"name": "Banquet", "capacity": 220},
                ],
                "operatingHours": [{"day": "Mon", "opens": "08:00", "closes": "22:00"}],
                "setupMinutes": 30,
                "turnaroundMinutes": 60,
                "isActive": True,
            }
        }
    )


def _required_text(value):
    """Name and location have to be real text, not a blank string."""
    if isinstance(value, str):
        value = value.strip()
    if not isinstance(value, str) or not value:
        raise ValueError("cannot be empty")
    return value


def _whole_minutes(value):
    """A setup or turnaround time is a whole number of minutes, zero or greater."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("must be a whole number of minutes")
    if value < 0:
        raise ValueError("must be zero or greater")
    return value


class VenueCreate(BaseModel):
    code: str = ""
    name: str
    location: str
    address: str = ""
    floor: str = ""
    description: str = ""
    facilities: list[str] = []
    accessibility: list[str] = []
    layouts: list[Layout] = []
    operatingHours: list[OperatingHours] = []
    setupMinutes: int
    turnaroundMinutes: int

    @field_validator("name", "location", mode="before")
    @classmethod
    def text_is_present(cls, value):
        return _required_text(value)

    @field_validator("setupMinutes", "turnaroundMinutes", mode="before")
    @classmethod
    def minutes_are_whole(cls, value):
        return _whole_minutes(value)


class VenueUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    location: str | None = None
    address: str | None = None
    floor: str | None = None
    description: str | None = None
    facilities: list[str] | None = None
    accessibility: list[str] | None = None
    layouts: list[Layout] | None = None
    operatingHours: list[OperatingHours] | None = None
    setupMinutes: int | None = None
    turnaroundMinutes: int | None = None

    @field_validator("name", "location", mode="before")
    @classmethod
    def text_is_present(cls, value):
        if value is None:
            raise ValueError("cannot be empty")
        return _required_text(value)

    @field_validator("setupMinutes", "turnaroundMinutes", mode="before")
    @classmethod
    def minutes_are_whole(cls, value):
        if value is None:
            raise ValueError("must be a whole number of minutes")
        return _whole_minutes(value)


class VenueActivityLogOut(BaseModel):
    logId: str
    venueId: str
    action: str
    changedBy: str
    changedByName: str
    changedByRole: str
    changes: dict
    createdAt: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "logId": "log-1",
                "venueId": "v1",
                "action": "updated",
                "changedBy": "u3",
                "changedByName": "Carol Venue",
                "changedByRole": "venue",
                "changes": {
                    "setupMinutes": {"old": 15, "new": 30},
                    "turnaroundMinutes": {"old": 45, "new": 60},
                },
                "createdAt": "2026-09-20T10:00:00",
            }
        }
    )


class VenueBookingCreate(BaseModel):
    venueId: str
    eventId: str
    startsAt: datetime
    endsAt: datetime
    requirementsSnapshot: str = ""
    coordinatorNotes: str = Field(default="", description="The coordinator's own notes for Venue Staff.")
    acknowledgeWarnings: bool = Field(
        default=False,
        description="Must be true to send a request for a venue whose suitability check has warnings.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "venueId": "v1",
                "eventId": "e1",
                "startsAt": "2026-10-06T09:00:00",
                "endsAt": "2026-10-06T17:00:00",
                "requirementsSnapshot": "Theatre layout, wheelchair access, PA system.",
            }
        }
    )


class VenueBookingDecision(BaseModel):
    reason: str | None = Field(default=None, description="Optional note stored on the booking.")

    model_config = ConfigDict(json_schema_extra={"example": {"reason": "Hall A is free that day."}})


class BookingReleaseRequest(BaseModel):
    """SPM-114: event cancellation asks venue-service to free every open booking."""

    eventId: str = Field(min_length=1)

    model_config = ConfigDict(json_schema_extra={"example": {"eventId": "e1"}})


class VenueArrangementOut(BaseModel):
    eventId: str
    complete: bool = Field(
        description="True only when the event has requested venues and every one of them is approved."
    )


class BookingReverificationRequest(BaseModel):
    """SPM-71 AC4: event-service asks for an event's confirmed bookings to be re-verified."""

    eventId: str = Field(min_length=1)
    reason: str = Field(default="", description="What changed on the event.")

    model_config = ConfigDict(
        json_schema_extra={"example": {"eventId": "e1", "reason": "Expected attendance: 120 -> 200"}}
    )


class VenueBookingOut(BaseModel):
    bookingId: str
    venueId: str
    eventId: str
    requestedBy: str
    status: str = Field(
        description="`pending`, `approved`, `rejected`, `withdrawn`, or `cancelled`."
    )
    startsAt: datetime
    endsAt: datetime
    setupStartsAt: datetime = Field(
        description="Start of the occupied window: the event start minus the venue's current setup time (SPM-112)."
    )
    teardownEndsAt: datetime = Field(
        description="End of the occupied window: the event end plus the venue's current turnaround time (SPM-112)."
    )
    requirementsSnapshot: str
    decisionReason: str | None
    reviewedBy: str | None
    reviewedAt: datetime | None
    createdAt: datetime
    eventSnapshot: dict | None = Field(
        default=None, description="The event's facts when the request was sent: name, client, times, needs."
    )
    coordinatorNotes: str = ""
    warnings: list[str] = Field(default=[], description="Suitability warnings the coordinator acknowledged.")
    venueName: str | None = None
    needsReverification: bool = Field(
        default=False, description="A significant event change may have invalidated this booking (SPM-71)."
    )
    reverificationNote: str | None = Field(default=None, description="What changed on the event.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bookingId": "bk-1",
                "venueId": "v1",
                "eventId": "e1",
                "requestedBy": "u2",
                "status": "pending",
                "startsAt": "2026-10-06T09:00:00",
                "endsAt": "2026-10-06T17:00:00",
                "setupStartsAt": "2026-10-06T08:00:00",
                "teardownEndsAt": "2026-10-06T18:00:00",
                "requirementsSnapshot": "Theatre layout, wheelchair access, PA system.",
                "decisionReason": None,
                "reviewedBy": None,
                "reviewedAt": None,
                "createdAt": "2026-09-20T10:00:00",
            }
        }
    )


class SuitabilityRequest(BaseModel):
    """SPM-62. Every field besides the two ids is optional: anything left out
    is taken from the event record, so a caller only sends what differs."""

    eventId: str
    venueId: str
    expectedAttendance: int | None = Field(default=None, ge=0, description="Defaults to the event's expected attendance.")
    layout: str | None = Field(default=None, description="Required layout. Defaults to the event's layout preference.")
    requiredFacilities: list[str] = []
    requiredAccessibility: list[str] = []
    startsAt: datetime | None = Field(default=None, description="Defaults to the event's proposed start.")
    endsAt: datetime | None = Field(default=None, description="Defaults to the event's proposed end.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "venueId": "v1",
                "requiredFacilities": ["Stage", "Video-conferencing"],
                "requiredAccessibility": ["Wheelchair accessible"],
            }
        }
    )


class VenueSearchResult(BaseModel):
    """SPM-61: one venue on the shortlist for an event's requirements."""

    venueId: str
    code: str
    name: str
    location: str
    capacity: int
    layout: str | None = Field(default=None, description="The layout searched for, when one was given.")
    layoutCapacity: int = Field(
        description="Capacity in the layout searched for, or the venue's overall capacity when no layout was given."
    )
    headroom: int = Field(description="`layoutCapacity` minus the expected attendance searched for.")
    setupMinutes: int
    turnaroundMinutes: int
    contested: bool = Field(
        description="True when another event's pending request overlaps this period. The venue is still shown."
    )


class ClashingBooking(BaseModel):
    """SPM-122: one of the two confirmed bookings in a clash, exactly as it stands."""

    bookingId: str
    eventId: str
    eventName: str | None = Field(
        default=None, description="The event's name as sent with the request; null for bookings older than SPM-63."
    )
    status: str
    startsAt: datetime
    endsAt: datetime
    setupStartsAt: datetime = Field(description="Start of the occupied window, from the venue's current setup time.")
    teardownEndsAt: datetime = Field(
        description="End of the occupied window, from the venue's current turnaround time."
    )


class BookingClashOut(BaseModel):
    """SPM-122: two confirmed bookings on one venue whose occupied windows overlap
    once the venue's current setup and turnaround times are applied. Listing a
    clash changes nothing about either booking or its event."""

    venueId: str
    venueName: str
    setupMinutes: int
    turnaroundMinutes: int
    first: ClashingBooking = Field(description="The booking whose occupied window starts first.")
    second: ClashingBooking
    overlapStartsAt: datetime = Field(description="When the two occupied windows start to overlap (UTC).")
    overlapEndsAt: datetime = Field(description="When they stop overlapping (UTC).")


class SuitabilityReason(BaseModel):
    severity: Literal["failure", "warning"]
    check: str = Field(description="Which rule produced this point, e.g. `capacity` or `clash`.")
    message: str


class SuitabilityOut(BaseModel):
    eventId: str
    venueId: str
    verdict: Literal["suitable", "suitable with warnings", "not suitable"]
    reasons: list[SuitabilityReason] = Field(description="Failures first, then warnings. Empty when suitable.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e4",
                "venueId": "v4",
                "verdict": "suitable with warnings",
                "reasons": [
                    {
                        "severity": "warning",
                        "check": "capacity",
                        "message": "Expected attendance of 19 is above 90% of what this venue can hold "
                        "in the Boardroom layout (20 people), so it will be a tight fit.",
                    }
                ],
            }
        }
    )


class EventFacts(BaseModel):
    """The parts of event-service's event record that venue-service uses:
    the suitability rule (SPM-62) and booking requests (SPM-63)."""

    expectedAttendance: int = 0
    layoutPreference: str | None = None
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    eventName: str = ""
    status: str = ""
    coordinatorId: str | None = None
    organisationId: str | None = None
    organisationName: str | None = None
    accessibilityNeeds: str = ""
    venueRequirements: str = ""
