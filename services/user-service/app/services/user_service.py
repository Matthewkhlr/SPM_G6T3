from sqlalchemy.orm import Session

from app.models.user import User
from shared.auth.tokens import create_access_token
from shared.exceptions.http import not_found, unauthorized


def login(db: Session, username: str, password: str) -> tuple[str, User]:
    if not username or not password:
        raise unauthorized("Invalid email or password.")
    user = db.query(User).filter(User.email == username).first()
    if not user or user.password != password:
        raise unauthorized("Invalid email or password.")
    token = create_access_token(
        {"sub": user.userId, "role": user.role, "name": user.userName, "email": user.email}
    )
    return token, user


def get_by_id(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.userId == user_id).first()
    if not user:
        raise not_found("User not found")
    return user


def list_users(db: Session) -> list[User]:
    return db.query(User).all()
