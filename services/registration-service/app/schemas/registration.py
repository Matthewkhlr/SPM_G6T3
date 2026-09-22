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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "attendeeRegistrationId": "r1",
                "eventId": "e1",
                "attendeeName": "Demo Attendee",
                "attendeeEmail": "one@example.com",
            }
        }
    )
