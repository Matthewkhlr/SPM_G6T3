from datetime import datetime

from pydantic import BaseModel


class VenueOut(BaseModel):
    venueId: str
    name: str
    location: str
    capacity: int
    facilities: list[str]
    accessibility: str
    layouts: list[str]
    operatingHours: str
    turnaroundMinutes: int


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
