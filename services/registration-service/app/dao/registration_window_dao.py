from app.models.registration_window import RegistrationWindow
from shared.dao.base import BaseDAO


class RegistrationWindowDAO(BaseDAO):
    def get_for_event(self, event_id: str) -> RegistrationWindow | None:
        return self.db.query(RegistrationWindow).filter(RegistrationWindow.eventId == event_id).first()
