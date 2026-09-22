from datetime import datetime

from pydantic import BaseModel, Field


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
    turnaroundMinutes: int
    isActive: bool


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
    turnaroundMinutes: int = 0


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
    turnaroundMinutes: int | None = None


class VenueActivityLogOut(BaseModel):
    logId: str
    venueId: str
    action: str
    changedBy: str
    changedByName: str
    changedByRole: str
    changes: dict
    createdAt: datetime


class VenueBookingCreate(BaseModel):
    venueId: str
    eventId: str
    startsAt: datetime
    endsAt: datetime
    setupStartsAt: datetime
    teardownEndsAt: datetime
    requirementsSnapshot: str = ""


class VenueBookingDecision(BaseModel):
    reason: str | None = None


class VenueBookingOut(BaseModel):
    bookingId: str
    venueId: str
    eventId: str
    requestedBy: str
    status: str
    startsAt: datetime
    endsAt: datetime
    setupStartsAt: datetime
    teardownEndsAt: datetime
    requirementsSnapshot: str
    decisionReason: str | None
    reviewedBy: str | None
    reviewedAt: datetime | None
    createdAt: datetime
