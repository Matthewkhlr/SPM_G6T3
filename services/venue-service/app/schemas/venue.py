from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
                "turnaroundMinutes": 60,
                "isActive": True,
            }
        }
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "logId": "log-1",
                "venueId": "v1",
                "action": "updated",
                "changedBy": "u3",
                "changedByName": "Carol Venue",
                "changedByRole": "venue",
                "changes": {"turnaroundMinutes": {"old": 45, "new": 60}},
                "createdAt": "2026-09-20T10:00:00",
            }
        }
    )


class VenueBookingCreate(BaseModel):
    venueId: str
    eventId: str
    startsAt: datetime
    endsAt: datetime
    setupStartsAt: datetime
    teardownEndsAt: datetime
    requirementsSnapshot: str = ""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "venueId": "v1",
                "eventId": "e1",
                "startsAt": "2026-10-06T09:00:00",
                "endsAt": "2026-10-06T17:00:00",
                "setupStartsAt": "2026-10-06T08:00:00",
                "teardownEndsAt": "2026-10-06T18:00:00",
                "requirementsSnapshot": "Theatre layout, wheelchair access, PA system.",
            }
        }
    )


class VenueBookingDecision(BaseModel):
    reason: str | None = Field(default=None, description="Optional note stored on the booking.")

    model_config = ConfigDict(json_schema_extra={"example": {"reason": "Hall A is free that day."}})


class VenueBookingOut(BaseModel):
    bookingId: str
    venueId: str
    eventId: str
    requestedBy: str
    status: str = Field(description="`pending`, `approved`, or `rejected`.")
    startsAt: datetime
    endsAt: datetime
    setupStartsAt: datetime
    teardownEndsAt: datetime
    requirementsSnapshot: str
    decisionReason: str | None
    reviewedBy: str | None
    reviewedAt: datetime | None
    createdAt: datetime

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
