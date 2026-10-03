from app.models.organisation import Organisation
from shared.dao.base import BaseDAO


class OrganisationDAO(BaseDAO):
    def list_all(self) -> list[Organisation]:
        return self.db.query(Organisation).all()
