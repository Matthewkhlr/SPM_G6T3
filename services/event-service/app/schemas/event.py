from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    status: str
    purpose: str
    description: str
    category: str | None = None
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    expectedAttendance: int
    venueRequirements: str
    accessibilityNeeds: str = ""
    equipmentRequirements: str
    layoutPreference: str | None = None
    registrationEnabled: bool
    registrationOpensAt: datetime | None = None
    registrationClosesAt: datetime | None = None
    capacity: int
    submittedAt: datetime | None = None
    organisationId: str | None = None
    organisationName: str | None = Field(
        default=None, description="Resolved from user-service; null if that service is down."
    )
    coordinatorId: str | None = None
    organiserContact: str = ""
    internalNotes: str | None = Field(
        default=None,
        description="Staff only. Null on every read an organiser or attendee can make.",
    )
    dateNear: bool = Field(
        default=False,
        description="True when proposedStartAt is within settings.event_proposed_date_near_days.",
    )
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


class EventDecision(BaseModel):
    reason: str | None = None


class EventActivityOut(BaseModel):
    """One activity-log entry: a status change, one field edited (SPM-71 AC5),
    or a coordinator assignment (SPM-66 AC4)."""

    historyId: str
    eventId: str
    kind: Literal["status", "edit", "assignment"] = "status"
    fromStatus: str | None = None
    toStatus: str | None = None
    field: str | None = Field(
        default=None, description="Edited field on `edit` entries; `coordinatorId` on `assignment` entries."
    )
    oldValue: str | None = Field(
        default=None, description="Previous value; the previous coordinator on `assignment` entries."
    )
    newValue: str | None = Field(
        default=None, description="New value; the assigned coordinator on `assignment` entries."
    )
    changedBy: str
    note: str = ""
    createdAt: datetime


def _naive_utc(value: datetime | None) -> datetime | None:
    """Stored datetimes are naive UTC, so an offset-aware input is converted
    first; otherwise comparing it with the stored value would always differ."""
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# SPM-71: a field left out of the body is not changed. These may not be
# cleared, because a planned event always needs them.
_REQUIRED_ON_EDIT = (
    "eventName",
    "purpose",
    "description",
    "proposedStartAt",
    "proposedEndAt",
    "expectedAttendance",
    "accessibilityNeeds",
    "equipmentRequirements",
)


class EventUpdate(BaseModel):
    """Fields the assigned coordinator can edit during planning (SPM-71).

    Only the fields present in the body change. Name, description, purpose,
    category, internal notes, and organiser contact save quietly (AC1); the
    rest are significant (AC2) and need `confirmSignificantChange` when the
    event holds a confirmed venue booking or equipment reservation (AC3).
    """

    eventName: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    purpose: str | None = None
    category: str | None = None
    internalNotes: str | None = None
    organiserContact: str | None = Field(default=None, max_length=255)
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    expectedAttendance: int | None = Field(default=None, ge=0)
    layoutPreference: str | None = None
    accessibilityNeeds: str | None = None
    equipmentRequirements: str | None = None
    confirmSignificantChange: bool = Field(
        default=False,
        description="Send true after the coordinator has seen which arrangements the change affects.",
    )

    @field_validator("proposedStartAt", "proposedEndAt")
    @classmethod
    def as_naive_utc(cls, value: datetime | None) -> datetime | None:
        return _naive_utc(value)

    @model_validator(mode="after")
    def check_values(self):
        for name in _REQUIRED_ON_EDIT:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared")
        if self.proposedStartAt and self.proposedEndAt and self.proposedEndAt <= self.proposedStartAt:
            raise ValueError("proposedEndAt must be after proposedStartAt")
        return self

    def changed_values(self) -> dict:
        """The fields the caller actually sent, without the confirmation flag."""
        return self.model_dump(exclude_unset=True, exclude={"confirmSignificantChange"})

    model_config = ConfigDict(
        json_schema_extra={"example": {"expectedAttendance": 200, "confirmSignificantChange": True}}
    )


class AffectedArrangement(BaseModel):
    kind: Literal["venue", "equipment"]
    id: str = Field(description="Venue booking id or equipment reservation id.")
    summary: str


class EventUpdateOut(EventOut):
    flaggedArrangements: list[AffectedArrangement] = Field(
        default=[], description="Venue bookings and equipment reservations now marked for re-verification."
    )


class SignificantFieldsOut(BaseModel):
    fields: list[str] = Field(description="Editing any of these can invalidate a booking or reservation.")
    quietFields: list[str] = Field(description="These save without any warning.")


class EventInternalNotesOut(BaseModel):
    eventId: str
    internalNotes: str = ""


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
    coordinatorId: str = Field(min_length=1, examples=["u2"])

    model_config = ConfigDict(json_schema_extra={"example": {"coordinatorId": "u2"}})


class CoordinatorCandidateOut(BaseModel):
    """SPM-66 AC2: a coordinator who can be assigned, with their workload for information only."""

    userId: str
    name: str
    email: str
    activeEventCount: int = Field(
        description="Assigned events that are not completed, cancelled, rejected, a draft, or discarded. "
        "Information only: no workload limit applies."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"userId": "u2", "name": "Ben Lee", "email": "coordinator@connectsphere.com", "activeEventCount": 3}
        }
    )


class EventCoordinatorOut(BaseModel):
    """SPM-66 AC5: who the organiser deals with. All null until a coordinator is assigned."""

    eventId: str
    coordinatorId: str | None = None
    name: str | None = None
    email: str | None = None


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
