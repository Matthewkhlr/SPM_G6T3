from sqlalchemy.orm import Session

from app.models.user import User
from shared.exceptions.http import not_found


def get_by_firebase_claims(db: Session, uid: str, email: str | None) -> User:
    """Resolve a verified Firebase token to a local user.

    Accounts are pre-seeded in this table before their matching Firebase
    account exists, so the first successful login for an email links the
    two by writing firebase_uid onto the existing row.
    """
    user = db.query(User).filter(User.firebaseUid == uid).first()
    if user:
        return user
    if not email:
        raise not_found("User not found")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise not_found("User not found")
    user.firebaseUid = uid
    db.commit()
    return user


def list_users(db: Session) -> list[User]:
    return db.query(User).all()
