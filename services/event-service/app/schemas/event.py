from datetime import datetime

from pydantic import BaseModel


class EventOut(BaseModel):
    eventId: str
    eventName: str
    status: str
    registrationEnabled: bool
    registrationOpensAt: datetime
    registrationClosesAt: datetime
    capacity: int
    registeredCount: int = 0
