"""Session holder shared by every data-access object.

Concrete DAOs keep their own queries. ``add`` is the only write that is the
same everywhere: attach a row to the current session. The service still commits.
"""

from sqlalchemy.orm import Session


class BaseDAO:
    def __init__(self, db: Session):
        self.db = db

    def add(self, row: object) -> None:
        self.db.add(row)
