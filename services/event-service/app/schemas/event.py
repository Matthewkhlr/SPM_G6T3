from datetime import datetime

from pydantic import BaseModel, Field, model_validator


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
    capacity: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_windows(self):
        if self.proposedEndAt <= self.proposedStartAt:
            raise ValueError("proposedEndAt must be after proposedStartAt")
        opens, closes = self.registrationOpensAt, self.registrationClosesAt
        if opens and closes and closes <= opens:
            raise ValueError("registrationClosesAt must be after registrationOpensAt")
        return self


class EventOut(BaseModel):
    eventId: str
    eventName: str
    status: str
    purpose: str
    description: str
    category: str | None = None
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    expectedAttendance: int
    venueRequirements: str
    equipmentRequirements: str
    registrationEnabled: bool
    registrationOpensAt: datetime | None = None
    registrationClosesAt: datetime | None = None
    capacity: int
    registeredCount: int = 0


class EventDecision(BaseModel):
    reason: str | None = None


class EventDraftUpsert(BaseModel):
    """Fields an organiser can save at draft stage — only eventName is required.

    Everything else may be omitted or left blank; a draft is, by definition,
    incomplete. Only checks that don't reject a partial draft run here.
    """

    eventName: str = Field(min_length=1, max_length=255)
    purpose: str = ""
    description: str = ""
    category: str | None = None
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    expectedAttendance: int | None = Field(default=None, ge=0)
    venueRequirements: str = ""
    equipmentRequirements: str = ""

    @model_validator(mode="after")
    def check_windows(self):
        if self.proposedStartAt and self.proposedEndAt and self.proposedEndAt <= self.proposedStartAt:
            raise ValueError("proposedEndAt must be after proposedStartAt")
        return self


class EventAssignmentCreate(BaseModel):
    coordinatorId: str = Field(min_length=1)


class EventAssignmentOut(BaseModel):
    assignmentId: str
    eventId: str
    coordinatorId: str
    assignedBy: str
    assignedAt: datetime