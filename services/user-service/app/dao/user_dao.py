from sqlalchemy.orm import Session

from app.models.user import User


class UserDAO:
    def __init__(self, db: Session):
        self.db = db

    def get_by_firebase_uid(self, uid: str) -> User | None:
        return self.db.query(User).filter(User.firebaseUid == uid).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def list_all(self) -> list[User]:
        return self.db.query(User).all()
