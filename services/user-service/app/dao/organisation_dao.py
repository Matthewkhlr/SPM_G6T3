from sqlalchemy.orm import Session

from app.models.organisation import Organisation


class OrganisationDAO:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[Organisation]:
        return self.db.query(Organisation).all()
