from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dao.organisation_dao import OrganisationDAO
from app.db.session import get_db
from app.schemas.organisation import OrganisationPublic
from shared.auth.deps import require_authenticated_user
from shared.openapi import error_responses

router = APIRouter(
    prefix="/organisations",
    tags=["organisations"],
    responses=error_responses(401),
)


def get_organisation_dao(db: Session = Depends(get_db)) -> OrganisationDAO:
    return OrganisationDAO(db)


@router.get(
    "",
    response_model=list[OrganisationPublic],
    summary="List organisations",
    description="Full organisation directory (id + name). Any authenticated caller can read this - "
    "other services use it to resolve organisationId to a display name, e.g. on the "
    "coordinator review queue.",
)
def list_organisations(
    dao: OrganisationDAO = Depends(get_organisation_dao),
    _claims: dict = Depends(require_authenticated_user),
):
    return dao.list_all()
