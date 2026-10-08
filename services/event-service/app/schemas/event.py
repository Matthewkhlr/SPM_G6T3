from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_serializer, model_validator


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
    expectedAttendance: int = Field(ge=1, description="At least one. A draft may still save zero.")
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
    preferredLocation: str = ""
    requiredFacilities: list[str] = Field(default_factory=list)
    accessibilityNote: str = ""
    accessibilitySelections: list[str] = Field(default_factory=list)
    equipmentLines: list[dict] = Field(default_factory=list)
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
    confirmedBy: str | None = Field(default=None, description="SPM-72: the coordinator who confirmed the event.")
    confirmedAt: datetime | None = Field(default=None, description="SPM-72: when the event was confirmed.")
    safetyReviewStatus: str | None = Field(
        default=None,
        description="SPM-121: the latest safety review's status (`pending`, `approved`, `rejected`, "
        "`changes_requested`, `superseded`). Only on `GET /events/mine`; null when never reviewed.",
    )
    hasOpenClarifications: bool = Field(
        default=False,
        description="True while any clarification on the event is still open (SPM-68). "
        "Approving it then needs `confirmOpenClarifications`.",
    )

    @model_serializer(mode="wrap")
    def _omit_empty_internal_notes(self, handler):
        # Organisers and attendees must not see the staff-notes field at all (SPM-15).
        data = handler(self)
        if data.get("internalNotes") is None:
            data.pop("internalNotes", None)
        return data

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


class EventApproval(BaseModel):
    """SPM-69: the assigned coordinator takes the request on."""

    note: str = Field(default="", max_length=2000, description="Optional. Shown to the organiser.")
    confirmOpenClarifications: bool = Field(
        default=False,
        description="Send true after the coordinator has been warned that clarifications are still open.",
    )

    model_config = ConfigDict(json_schema_extra={"example": {"note": "Ready for planning"}})


class EventApprovalOut(EventOut):
    """SPM-69 AC2: the approved event, with who approved it, when, and the note."""

    decision: Literal["approved"] = "approved"
    decisionNote: str = ""
    decidedBy: str
    decidedAt: datetime


class EventDecisionOut(BaseModel):
    """SPM-69 AC3: the latest decision on a request. All null until one is made."""

    eventId: str
    decision: Literal["approved", "rejected"] | None = None
    decisionNote: str | None = None
    decidedBy: str | None = None
    decidedAt: datetime | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "decision": "approved",
                "decisionNote": "Ready for planning",
                "decidedBy": "u2",
                "decidedAt": "2026-10-02T09:00:00",
            }
        }
    )


def _required_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class ClarificationCreate(BaseModel):
    """SPM-68 AC1: what is unclear, and optionally the event field it concerns."""

    message: str = Field(min_length=1, max_length=2000)
    field: str | None = Field(
        default=None, description="An event request field, e.g. `expectedAttendance`. Must be one of EventCreate's fields."
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("field")
    @classmethod
    def known_field(cls, value: str | None) -> str | None:
        if not value:
            return None
        if value not in EventCreate.model_fields:
            raise ValueError(f"{value} is not a field of an event request")
        return value

    model_config = ConfigDict(
        json_schema_extra={"example": {"message": "Please confirm expected attendance.", "field": "expectedAttendance"}}
    )


class ClarificationReplyCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        return _required_text(value)

    model_config = ConfigDict(json_schema_extra={"example": {"message": "Attendance stays at 80."}})


class ClarificationEntryOut(BaseModel):
    """SPM-68 AC3: one entry in a thread, with its author, their role, and when."""

    entryId: str
    authorId: str
    authorName: str | None = Field(default=None, description="Null if user-service could not be reached.")
    authorRole: str
    message: str
    createdAt: datetime


class ClarificationOut(BaseModel):
    """SPM-68: one clarification and its thread. `entries` starts with the
    question itself, then every reply, oldest first."""

    clarificationId: str
    eventId: str
    message: str
    field: str | None = None
    status: Literal["open", "resolved"]
    raisedBy: str
    createdAt: datetime
    resolvedBy: str | None = None
    resolvedAt: datetime | None = None
    entries: list[ClarificationEntryOut]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "clarificationId": "rv-clarify-e3",
                "eventId": "e3",
                "message": "Please confirm expected attendance.",
                "field": "expectedAttendance",
                "status": "open",
                "raisedBy": "u2",
                "createdAt": "2026-10-01T09:00:00",
                "resolvedBy": None,
                "resolvedAt": None,
                "entries": [
                    {
                        "entryId": "rv-clarify-e3",
                        "authorId": "u2",
                        "authorName": "Ben Lee",
                        "authorRole": "coordinator",
                        "message": "Please confirm expected attendance.",
                        "createdAt": "2026-10-01T09:00:00",
                    },
                    {
                        "entryId": "reply-1",
                        "authorId": "u1",
                        "authorName": "Alice Tan",
                        "authorRole": "organiser",
                        "message": "Attendance stays at 80.",
                        "createdAt": "2026-10-01T11:30:00",
                    },
                ],
            }
        }
    )


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


class RegistrationSettingsUpdate(BaseModel):
    """SPM-90: what the assigned coordinator can set during planning. Only the
    fields present in the body change. The period may be cleared (it is then
    still to be set); whether registration is needed and the capacity may not."""

    registrationEnabled: bool | None = None
    registrationOpensAt: datetime | None = None
    registrationClosesAt: datetime | None = None
    capacity: int | None = Field(default=None, ge=0)
    confirmOverVenueCapacity: bool = Field(
        default=False,
        description="Send true after the coordinator has seen that the capacity exceeds the booked venue's.",
    )
    confirmRegistrationOff: bool = Field(
        default=False,
        description="Send true after the coordinator has seen how many attendees turning registration off affects.",
    )

    @field_validator("registrationOpensAt", "registrationClosesAt")
    @classmethod
    def as_naive_utc(cls, value: datetime | None) -> datetime | None:
        # Stored to the second, so a value read back and sent again is not an edit.
        value = _naive_utc(value)
        return value.replace(microsecond=0) if value else value

    @model_validator(mode="after")
    def check_values(self):
        for name in ("registrationEnabled", "capacity"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared")
        return self

    def changed_values(self) -> dict:
        """The fields the caller actually sent, without the confirmation flags."""
        return self.model_dump(exclude_unset=True, exclude={"confirmOverVenueCapacity", "confirmRegistrationOff"})

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "registrationEnabled": True,
                "registrationOpensAt": "2026-10-10T09:00:00",
                "registrationClosesAt": "2026-10-28T18:00:00",
                "capacity": 80,
            }
        }
    )


class RegistrationSettingsOut(EventOut):
    notifiedAttendees: int = Field(
        default=0, description="Registered attendees told that registration was turned off (SPM-90 AC5)."
    )


class AffectedArrangement(BaseModel):
    kind: Literal["venue", "equipment"]
    id: str = Field(description="Venue booking id or equipment reservation id.")
    summary: str


class EventUpdateOut(EventOut):
    flaggedArrangements: list[AffectedArrangement] = Field(
        default=[], description="Venue bookings and equipment reservations now marked for re-verification."
    )


# SPM-106 AC3: what an organiser can ask to change. The date is part of the
# start and end.
CHANGEABLE_FIELDS = (
    "eventName",
    "description",
    "purpose",
    "category",
    "proposedStartAt",
    "proposedEndAt",
    "expectedAttendance",
    "layoutPreference",
    "accessibilityNeeds",
    "equipmentRequirements",
)


class ChangeRequestCreate(BaseModel):
    """SPM-106 AC2: the fields to change with their proposed values, and why.
    Proposed values follow the same rules as a coordinator's edit (SPM-71)."""

    reason: str = Field(min_length=1, max_length=2000)
    proposedChanges: dict[str, Any] = Field(min_length=1, description="Field name -> proposed value.")

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("proposedChanges")
    @classmethod
    def changeable_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        unknown = sorted(set(value) - set(CHANGEABLE_FIELDS))
        if unknown:
            raise ValueError(f"These fields cannot be changed by request: {', '.join(unknown)}")
        try:
            update = EventUpdate(**value)
        except ValidationError as exc:
            raise ValueError("; ".join(f"{'.'.join(map(str, e['loc'])) or 'value'}: {e['msg']}" for e in exc.errors()))
        # Stored as JSON, so datetimes become ISO strings in naive UTC.
        return update.model_dump(mode="json", exclude_unset=True, exclude={"confirmSignificantChange"})

    model_config = ConfigDict(
        json_schema_extra={"example": {"reason": "Client wants a banquet dinner", "proposedChanges": {"layoutPreference": "Banquet"}}}
    )


class ChangeRequestAccept(BaseModel):
    reason: str = Field(default="", max_length=2000, description="Optional; shown to the organiser.")
    confirmSignificantChange: bool = Field(
        default=False,
        description="Send true after seeing which arrangements applying the change affects (as for PATCH /events/{id}).",
    )


class ChangeRequestDecline(BaseModel):
    reason: str = Field(min_length=1, max_length=2000, description="Why the change was declined; shown to the organiser.")

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        return _required_text(value)


class ChangeRequestOut(BaseModel):
    changeRequestId: str
    eventId: str
    status: str = Field(description="`pending`, `withdrawn`, `accepted`, or `declined`; older rows may read `applied`.")
    reason: str
    proposedChanges: dict[str, Any]
    currentValues: dict[str, Any] | None = Field(default=None, description="Each field's value when the request was raised.")
    requestedBy: str
    createdAt: datetime
    affectsVenue: bool
    affectsEquipment: bool
    affectsRegistration: bool
    reviewedBy: str | None = Field(default=None, description="Who closed it: the deciding coordinator, or the organiser who withdrew.")
    reviewedAt: datetime | None = None
    decisionReason: str | None = None
    flaggedArrangements: list[AffectedArrangement] = Field(
        default=[], description="On accept: venue bookings and equipment reservations now marked for re-verification."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "changeRequestId": "cr-1",
                "eventId": "e3",
                "status": "pending",
                "reason": "Client wants a banquet dinner",
                "proposedChanges": {"layoutPreference": "Banquet"},
                "currentValues": {"layoutPreference": "Theatre"},
                "requestedBy": "u1",
                "createdAt": "2026-10-02T09:00:00",
                "affectsVenue": True,
                "affectsEquipment": False,
                "affectsRegistration": False,
            }
        }
    )


class SafetySubmission(BaseModel):
    """SPM-120: what the coordinator adds when submitting for a safety review."""

    crowdMovement: str = Field(
        min_length=1, max_length=4000, description="How people arrive, move through, and leave the venue."
    )
    equipmentPlacement: str = Field(
        default="",
        max_length=4000,
        description="Where each piece of equipment goes. Required when equipment is reserved for the event.",
    )

    @field_validator("crowdMovement")
    @classmethod
    def crowd_movement_not_blank(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("equipmentPlacement")
    @classmethod
    def trim_placement(cls, value: str) -> str:
        return value.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "crowdMovement": "Guests enter by the lift lobby and leave by the promenade doors; aisles stay 2 m wide.",
                "equipmentPlacement": "Projector at the back of the hall; PA speakers either side of the stage, clear of exits.",
            }
        }
    )


class SafetyApproval(BaseModel):
    note: str = Field(default="", max_length=2000, description="Optional; shown to the coordinator and organiser.")


class SafetyRejection(BaseModel):
    reason: str = Field(min_length=1, max_length=2000, description="Why the plan is unsafe. Required.")

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        return _required_text(value)


class SafetyChangeRequest(BaseModel):
    requiredChanges: str = Field(min_length=1, max_length=4000, description="What must change. Required.")
    affected: list[Literal["venue", "technical"]] = Field(
        default=[], description="Arrangements to flag so venue staff or technical support review them again."
    )

    @field_validator("requiredChanges")
    @classmethod
    def changes_not_blank(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("affected")
    @classmethod
    def no_repeats(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class SafetyVenueFacts(BaseModel):
    venueId: str
    venueName: str
    location: str = ""
    startsAt: datetime
    endsAt: datetime
    layout: str | None = Field(default=None, description="The event's layout, when the venue offers it.")
    capacityInLayout: int = Field(description="What the venue holds in that layout; its largest layout otherwise.")
    venueCapacity: int
    layouts: list[dict] = []
    accessibilityFeatures: list[str] = []
    emergencyAccess: str = ""
    restrictions: str = ""
    operatingHours: list[dict] = []
    needsReverification: bool = False
    reverificationNote: str | None = None


class SafetyEquipmentLine(BaseModel):
    equipmentId: str
    name: str
    quantity: int
    status: str
    technicalRequirements: str = ""
    needsReverification: bool = False


class SafetyPackage(BaseModel):
    """SPM-120 AC2: everything the Safety Officer judges, as it stood when submitted."""

    eventName: str
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    expectedAttendance: int
    layout: str | None = None
    accessibilityRequirements: list[str] = []
    accessibilityNote: str = ""
    venues: list[SafetyVenueFacts]
    equipment: list[SafetyEquipmentLine] = []
    crowdMovement: str
    equipmentPlacement: str = ""


class ConfirmationGap(BaseModel):
    """One thing standing between the event and Confirmed (SPM-72 AC2)."""

    kind: Literal["venue", "equipment", "safety", "status"]
    message: str
    equipmentId: str | None = Field(
        default=None, description="On an equipment line that can be recorded as not required."
    )


class ConfirmationOut(BaseModel):
    eventId: str
    ready: bool = Field(description="True when nothing is missing and the coordinator can confirm.")
    missing: list[ConfirmationGap] = []


class EventConfirmOut(EventOut):
    """SPM-72 AC3: the confirmed event, with who confirmed it and when."""

    decidedBy: str
    decidedAt: datetime


class EquipmentNotRequired(BaseModel):
    reason: str = Field(min_length=1, max_length=2000, description="Why this equipment is no longer needed.")

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        return _required_text(value)


class SafetyReviewOut(BaseModel):
    reviewId: str
    eventId: str
    status: Literal["pending", "approved", "rejected", "changes_requested", "superseded"]
    submittedBy: str
    submittedAt: datetime
    package: SafetyPackage
    decidedBy: str | None = Field(default=None, description="The officer who decided, or who changed the event (superseded).")
    decidedAt: datetime | None = None
    decisionNote: str | None = Field(
        default=None, description="Approval note, rejection reason, required changes, or what changed (superseded)."
    )
    affected: list[str] = Field(default=[], description="Arrangements flagged for re-checking (changes requested).")
    flaggedArrangements: list[AffectedArrangement] = Field(
        default=[], description="On request changes: the bookings and reservations now marked for re-checking."
    )


class ChangeableFieldsOut(BaseModel):
    fields: list[str] = Field(description="Fields an organiser can ask to change (SPM-106 AC3).")


class SignificantFieldsOut(BaseModel):
    fields: list[str] = Field(description="Editing any of these can invalidate a booking or reservation.")
    quietFields: list[str] = Field(description="These save without any warning.")


class EventInternalNotesOut(BaseModel):
    eventId: str
    internalNotes: str = ""


class EquipmentLineIn(BaseModel):
    """One equipment requirement. A type from the catalogue, never a unit id."""

    equipmentId: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    technicalNotes: str = ""

    @field_validator("quantity", mode="before")
    @classmethod
    def whole_quantity(cls, value):
        if isinstance(value, bool) or isinstance(value, float):
            raise ValueError("quantity must be a whole number of at least 1")
        return value


class OrganiserDraftPatch(BaseModel):
    """Fields an organiser can change on their own draft (SPM-80). Only fields sent are saved."""

    eventName: str | None = Field(default=None, min_length=1, max_length=255)
    purpose: str | None = None
    description: str | None = None
    category: str | None = None
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    expectedAttendance: int | None = Field(default=None, ge=0)
    venueRequirements: str | None = None
    equipmentRequirements: str | None = None
    layoutPreference: str | None = None
    preferredLocation: str | None = None
    requiredFacilities: list[str] | None = None
    accessibilityNeeds: str | list[str] | None = None
    accessibilityNote: str | None = None
    equipmentLines: list[EquipmentLineIn] | None = None

    @field_validator("proposedStartAt", "proposedEndAt")
    @classmethod
    def as_naive_utc(cls, value: datetime | None) -> datetime | None:
        return _naive_utc(value)

    @model_validator(mode="after")
    def check_windows(self):
        if self.proposedStartAt and self.proposedEndAt and self.proposedEndAt <= self.proposedStartAt:
            raise ValueError("proposedEndAt must be after proposedStartAt")
        return self


class RequirementOptionsOut(BaseModel):
    layouts: list[str]
    facilities: list[str]
    accessibility: list[str]


class EventIntake(BaseModel):
    """POST /events. A name alone saves a draft; dates and attendance submit it."""

    eventName: str = Field(min_length=1, max_length=255)
    purpose: str = ""
    description: str = ""
    category: str | None = None
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    expectedAttendance: int | None = Field(default=None, ge=0)
    venueRequirements: str = ""
    accessibilityNeeds: str = ""
    equipmentRequirements: str = ""
    layoutPreference: str | None = None
    registrationEnabled: bool = False
    registrationOpensAt: datetime | None = None
    registrationClosesAt: datetime | None = None
    capacity: int = Field(default=0, ge=0)

    def to_create(self) -> EventCreate:
        return EventCreate(
            eventName=self.eventName,
            purpose=self.purpose,
            description=self.description,
            category=self.category,
            proposedStartAt=self.proposedStartAt,
            proposedEndAt=self.proposedEndAt,
            expectedAttendance=self.expectedAttendance if self.expectedAttendance is not None else 1,
            venueRequirements=self.venueRequirements,
            accessibilityNeeds=self.accessibilityNeeds,
            equipmentRequirements=self.equipmentRequirements,
            layoutPreference=self.layoutPreference,
            registrationEnabled=self.registrationEnabled,
            registrationOpensAt=self.registrationOpensAt,
            registrationClosesAt=self.registrationClosesAt,
            capacity=self.capacity,
        )

    def to_draft(self) -> "EventDraftUpsert":
        return EventDraftUpsert(
            eventName=self.eventName,
            purpose=self.purpose,
            description=self.description,
            category=self.category,
            proposedStartAt=self.proposedStartAt,
            proposedEndAt=self.proposedEndAt,
            expectedAttendance=self.expectedAttendance,
            venueRequirements=self.venueRequirements,
            equipmentRequirements=self.equipmentRequirements,
            layoutPreference=self.layoutPreference,
        )


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
    layoutPreference: str | None = None
    preferredLocation: str = ""
    requiredFacilities: list[str] = Field(default_factory=list)
    accessibilityNeeds: str | list[str] = ""
    accessibilityNote: str = ""
    equipmentLines: list[EquipmentLineIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_windows(self):
        if self.proposedStartAt and self.proposedEndAt and self.proposedEndAt <= self.proposedStartAt:
            raise ValueError("proposedEndAt must be after proposedStartAt")
        return self


class EventAssignmentCreate(BaseModel):
    coordinatorId: str = Field(min_length=1, examples=["u2"])

    model_config = ConfigDict(json_schema_extra={"example": {"coordinatorId": "u2"}})


class RegistrationAccessOut(BaseModel):
    """Registration facts for the organiser or assigned coordinator.

    organiserId is not included. Callers who are not that organiser or
    coordinator are refused before this payload is built.
    """

    eventId: str
    registrationEnabled: bool
    registrationOpensAt: datetime | None = None
    registrationClosesAt: datetime | None = None
    capacity: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "registrationEnabled": True,
                "registrationOpensAt": "2026-09-17T00:00:00",
                "registrationClosesAt": "2026-10-03T23:59:59",
                "capacity": 3,
            }
        }
    )


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
