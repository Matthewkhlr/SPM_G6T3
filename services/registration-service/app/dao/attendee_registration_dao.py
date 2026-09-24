from sqlalchemy.orm import Session

from app.models.attendee_registration import AttendeeRegistration


class AttendeeRegistrationDAO:
    def __init__(self, db: Session):
        self.db = db

    def list_for_event(self, event_id: str) -> list[AttendeeRegistration]:
        return (
            self.db.query(AttendeeRegistration)
            .filter(
                AttendeeRegistration.eventId == event_id,
                AttendeeRegistration.status == "registered",
            )
            .all()
        )

    def add(self, row: AttendeeRegistration) -> None:
        self.db.add(row)
