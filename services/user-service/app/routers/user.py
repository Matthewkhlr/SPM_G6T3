from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserPublic
from app.services import user_service
from shared.auth.deps import require_authenticated_user

router = APIRouter(prefix="/users", tags=["users"])


def current_user(claims: dict = Depends(require_authenticated_user), db: Session = Depends(get_db)):
    return user_service.get_by_firebase_claims(db, claims["uid"], claims.get("email"))


@router.get("/me", response_model=UserPublic)
def me(user=Depends(current_user)):
    return user


@router.get("", response_model=list[UserPublic])
def list_users(db: Session = Depends(get_db), _user=Depends(current_user)):
    return user_service.list_users(db)
