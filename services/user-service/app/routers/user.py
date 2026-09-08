from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import LoginRequest, LoginResponse, UserPublic
from app.services import user_service
from shared.auth.tokens import verify_bearer_token
from shared.exceptions.http import unauthorized

router = APIRouter(prefix="/users", tags=["users"])


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise unauthorized()
    try:
        payload = verify_bearer_token(authorization[7:])
    except ValueError:
        raise unauthorized("Invalid or expired token")
    return user_service.get_by_id(db, payload["sub"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    token, user = user_service.login(db, body.username, body.password)
    return LoginResponse(token=token, user=UserPublic.model_validate(user))


@router.get("/me", response_model=UserPublic)
def me(user=Depends(current_user)):
    return user


@router.get("", response_model=list[UserPublic])
def list_users(db: Session = Depends(get_db), _user=Depends(current_user)):
    return user_service.list_users(db)
