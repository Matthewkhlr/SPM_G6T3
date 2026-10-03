from app.models.user import User
from shared.dao.base import BaseDAO


class UserDAO(BaseDAO):
    def get_by_firebase_uid(self, uid: str) -> User | None:
        return self.db.query(User).filter(User.firebaseUid == uid).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def list_all(self) -> list[User]:
        return self.db.query(User).all()
