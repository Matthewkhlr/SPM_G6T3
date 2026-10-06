from datetime import datetime

from pydantic import BaseModel, Field


class AttachmentIn(BaseModel):
    name: str = ""
    url: str = ""


class ReadinessCreate(BaseModel):
    category: str = Field(min_length=1)
    handlerId: str = Field(min_length=1)
    status: str = "outstanding"
    note: str = ""
    dueAt: datetime | None = None
    attachments: list[AttachmentIn] = Field(default_factory=list)


class ReadinessPatch(BaseModel):
    category: str | None = None
    handlerId: str | None = None
    status: str | None = None
    note: str | None = None
    dueAt: datetime | None = None
    attachments: list[AttachmentIn] | None = None


class ReadinessItemOut(BaseModel):
    itemId: str
    eventId: str
    category: str
    handlerId: str = ""
    handlerName: str = ""
    personnel: str = ""
    handlerEmail: str = ""
    handlerPhone: str = ""
    status: str
    note: str = ""
    assignedAt: datetime
    dueAt: datetime | None = None
    dueSoon: bool = False
    alert: bool = False
    overdue: bool = False
    attachments: list[dict] = Field(default_factory=list)


class OpenEventOut(BaseModel):
    eventId: str
    eventName: str
    status: str
    category: str | None = None
    description: str = ""
    purpose: str = ""
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    startsAt: datetime | None = None
    endsAt: datetime | None = None
    accessibilityNeeds: str = ""
    layoutPreference: str | None = None
    registrationClosesAt: datetime | None = None
    capacity: int = 0
    registeredCount: int = 0
    remaining: int = 0
    full: bool = False
    venueName: str = ""
    venueLocation: str = ""
    changedAt: datetime | None = None
