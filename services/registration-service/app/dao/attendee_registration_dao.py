from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.attendee_registration import AttendeeRegistration


class AttendeeRegistrationDAO:
    def __init__(self, db: Session):
        self.db = db

    def get(self, registration_id: str) -> AttendeeRegistration | None:
        return self.db.get(AttendeeRegistration, registration_id)

    def list_for_event(self, event_id: str) -> list[AttendeeRegistration]:
        return (
            self.db.query(AttendeeRegistration)
            .filter(
                AttendeeRegistration.eventId == event_id,
                AttendeeRegistration.status == "registered",
            )
            .all()
        )

    def list_all_for_event(self, event_id: str) -> list[AttendeeRegistration]:
        return (
            self.db.query(AttendeeRegistration)
            .filter(AttendeeRegistration.eventId == event_id)
            .order_by(AttendeeRegistration.createdAt.asc())
            .all()
        )

    def find_for_event_email(
        self, event_id: str, email: str, status: str | None = None
    ) -> AttendeeRegistration | None:
        query = self.db.query(AttendeeRegistration).filter(
            AttendeeRegistration.eventId == event_id,
            func.lower(AttendeeRegistration.attendeeEmail) == email.lower(),
        )
        if status is not None:
            query = query.filter(AttendeeRegistration.status == status)
        return query.order_by(AttendeeRegistration.createdAt.desc()).first()

    def list_for_email(self, email: str) -> list[AttendeeRegistration]:
        return (
            self.db.query(AttendeeRegistration)
            .filter(func.lower(AttendeeRegistration.attendeeEmail) == email.lower())
            .order_by(AttendeeRegistration.createdAt.asc())
            .all()
        )

    def list_owned(self, user_id: str | None, email: str | None) -> list[AttendeeRegistration]:
        filters = []
        if user_id:
            filters.append(AttendeeRegistration.userId == user_id)
        if email:
            filters.append(func.lower(AttendeeRegistration.attendeeEmail) == email.lower())
        if not filters:
            return []
        return (
            self.db.query(AttendeeRegistration)
            .filter(or_(*filters))
            .order_by(AttendeeRegistration.createdAt.asc())
            .all()
        )

    def add(self, row: AttendeeRegistration) -> None:
        self.db.add(row)
