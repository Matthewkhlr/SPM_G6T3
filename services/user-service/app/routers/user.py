from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserPublic
from app.services import user_service
from shared.auth.deps import require_authenticated_user
from shared.openapi import error_responses

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses=error_responses(401),
)


def current_user(claims: dict = Depends(require_authenticated_user), db: Session = Depends(get_db)):
    return user_service.get_by_firebase_claims(db, claims["uid"], claims.get("email"))


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Current user",
    description="Resolves the Firebase token to the local user row (links `firebase_uid` on first successful login).",
    responses=error_responses(404),
)
def me(user=Depends(current_user)):
    return user


@router.get(
    "",
    response_model=list[UserPublic],
    summary="List users",
    description="Full user directory. Any authenticated user can call this.",
)
def list_users(db: Session = Depends(get_db), _user=Depends(current_user)):
    return user_service.list_users(db)
