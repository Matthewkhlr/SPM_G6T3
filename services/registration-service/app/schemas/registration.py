from pydantic import BaseModel


class RegisterRequest(BaseModel):
    eventId: str
    name: str
    email: str


class AttendeeOut(BaseModel):
    attendeeRegistrationId: str
    eventId: str
    attendeeName: str
    attendeeEmail: str
