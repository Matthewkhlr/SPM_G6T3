from sqlalchemy.orm import Session

from app.models.registration_window import RegistrationWindow


class RegistrationWindowDAO:
    def __init__(self, db: Session):
        self.db = db

    def get_for_event(self, event_id: str) -> RegistrationWindow | None:
        return self.db.query(RegistrationWindow).filter(RegistrationWindow.eventId == event_id).first()
