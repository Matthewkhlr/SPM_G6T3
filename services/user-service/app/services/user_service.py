from sqlalchemy.orm import Session

from app.dao.user_dao import UserDAO
from app.models.user import User
from shared.exceptions.http import not_found


class UserService:
    def __init__(self, db: Session, user_dao: UserDAO):
        self.db = db
        self.user_dao = user_dao

    def get_by_firebase_claims(self, uid: str, email: str | None) -> User:
        """Resolve a verified Firebase token to a local user.

        Accounts are pre-seeded in this table before their matching Firebase
        account exists, so the first successful login for an email links the
        two by writing firebase_uid onto the existing row.
        """
        user = self.user_dao.get_by_firebase_uid(uid)
        if user:
            return user
        if not email:
            raise not_found("User not found")
        user = self.user_dao.get_by_email(email)
        if not user:
            raise not_found("User not found")
        user.firebaseUid = uid
        self.db.commit()
        return user

    def list_users(self) -> list[User]:
        return self.user_dao.list_all()
