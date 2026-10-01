from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RegisterRequest(BaseModel):
    eventId: str
    name: str
    email: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "name": "Amy Wong",
                "email": "attendee@connectsphere.com",
            }
        }
    )


class AttendeeOut(BaseModel):
    attendeeRegistrationId: str
    eventId: str
    attendeeName: str
    attendeeEmail: str
    status: str = "registered"
    createdAt: datetime | None = None
    withdrawnAt: datetime | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "attendeeRegistrationId": "r1",
                "eventId": "e1",
                "attendeeName": "Demo Attendee",
                "attendeeEmail": "one@example.com",
                "status": "registered",
                "createdAt": "2026-09-20T09:00:00",
                "withdrawnAt": None,
            }
        }
    )


class RegistrationRosterOut(BaseModel):
    eventId: str
    capacity: int
    registered: int
    withdrawn: int
    remaining: int
    remainingPlaces: int
    placesRemaining: int
    registrationOpensAt: datetime | None = None
    registrationClosesAt: datetime | None = None
    attendees: list[AttendeeOut]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "capacity": 3,
                "registered": 1,
                "withdrawn": 0,
                "remaining": 2,
                "remainingPlaces": 2,
                "placesRemaining": 2,
                "registrationOpensAt": "2026-09-17T00:00:00",
                "registrationClosesAt": "2026-10-03T23:59:59",
                "attendees": [],
            }
        }
    )


class RegistrationCountOut(BaseModel):
    count: int
