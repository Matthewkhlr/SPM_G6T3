from sqlalchemy.orm import Session

from app.models.event_assignment import EventAssignment


class EventAssignmentDAO:
    def __init__(self, db: Session):
        self.db = db

    def add(self, row: EventAssignment) -> None:
        self.db.add(row)
