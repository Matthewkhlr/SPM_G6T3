from pydantic import BaseModel


class VenueOut(BaseModel):
    venueId: str
    name: str
    location: str
    capacity: int
    facilities: list[str]
    accessibility: str
    layouts: list[str]
    operatingHours: str
    turnaroundMinutes: int
