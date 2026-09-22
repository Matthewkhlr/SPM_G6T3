from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventCreate(BaseModel):
    """Fields an organiser supplies when creating an event request.

    organiserId / organisationId are deliberately absent: they come from the
    caller's verified identity, not the request body, so a client cannot file
    an event in someone else's name. status/submittedAt are set by the service.
    """

    eventName: str = Field(min_length=1, max_length=255)
    purpose: str = ""
    description: str = ""
    category: str | None = None
    proposedStartAt: datetime
    proposedEndAt: datetime
    expectedAttendance: int = Field(ge=0)
    venueRequirements: str = ""
    accessibilityNeeds: str = ""
    equipmentRequirements: str = ""
    layoutPreference: str | None = None
    registrationEnabled: bool = False
    registrationOpensAt: datetime | None = None
    registrationClosesAt: datetime | None = None
    capacity: int = Field(default=0, ge=0, description="Intended registration cap.")

    @model_validator(mode="after")
    def check_windows(self):
        if self.proposedEndAt <= self.proposedStartAt:
            raise ValueError("proposedEndAt must be after proposedStartAt")
        opens, closes = self.registrationOpensAt, self.registrationClosesAt
        if opens and closes and closes <= opens:
            raise ValueError("registrationClosesAt must be after registrationOpensAt")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventName": "AI in Events Summit",
                "purpose": "Share AI practices for event operations.",
                "description": "A one-day summit for ConnectSphere clients.",
                "category": "conference",
                "proposedStartAt": "2026-10-06T09:00:00",
                "proposedEndAt": "2026-10-06T17:00:00",
                "expectedAttendance": 120,
                "venueRequirements": "Large hall with stage and video-conferencing.",
                "accessibilityNeeds": "Wheelchair access required.",
                "equipmentRequirements": "Projector and PA system.",
                "layoutPreference": "Theatre",
                "registrationEnabled": True,
                "registrationOpensAt": "2026-09-17T00:00:00",
                "registrationClosesAt": "2026-10-03T23:59:59",
                "capacity": 120,
            }
        }
    )


class EventOut(BaseModel):
    eventId: str
    eventName: str
    status: str = Field(
        description="Create API writes `created`. Seed data also uses `planning` and `confirmed`."
    )
    proposedStartAt: datetime
    proposedEndAt: datetime
    registrationEnabled: bool
    registrationOpensAt: datetime | None = None
    registrationClosesAt: datetime | None = None
    capacity: int
    registeredCount: int = Field(
        default=0, description="Live count from registration-service; 0 if that service is down."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "eventName": "AI in Events Summit",
                "status": "confirmed",
                "proposedStartAt": "2026-10-06T09:00:00",
                "proposedEndAt": "2026-10-06T17:00:00",
                "registrationEnabled": True,
                "registrationOpensAt": "2026-09-17T00:00:00",
                "registrationClosesAt": "2026-10-03T23:59:59",
                "capacity": 3,
                "registeredCount": 1,
            }
        }
    )


class EventAssignmentCreate(BaseModel):
    coordinatorId: str = Field(min_length=1, examples=["u2"])

    model_config = ConfigDict(json_schema_extra={"example": {"coordinatorId": "u2"}})


class EventAssignmentOut(BaseModel):
    assignmentId: str
    eventId: str
    coordinatorId: str
    assignedBy: str
    assignedAt: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assignmentId": "asgn-e1",
                "eventId": "e1",
                "coordinatorId": "u2",
                "assignedBy": "u2",
                "assignedAt": "2026-09-02T10:00:00",
            }
        }
    )
