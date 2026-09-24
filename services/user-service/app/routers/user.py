from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dao.user_dao import UserDAO
from app.db.session import get_db
from app.schemas.user import UserPublic
from app.services.user_service import UserService
from shared.auth.deps import require_authenticated_user
from shared.openapi import error_responses

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses=error_responses(401),
)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db, UserDAO(db))


def current_user(
    claims: dict = Depends(require_authenticated_user),
    service: UserService = Depends(get_user_service),
):
    return service.get_by_firebase_claims(claims["uid"], claims.get("email"))


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
def list_users(service: UserService = Depends(get_user_service), _user=Depends(current_user)):
    return service.list_users()
