"""Session owner for a use case.

Subclasses inject their DAOs and decide when to commit. ``_require`` turns a
missing row into a 404 so each service does not repeat that check.
"""

from typing import TypeVar

from sqlalchemy.orm import Session

from shared.exceptions.http import not_found

Row = TypeVar("Row")


class BaseService:
    def __init__(self, db: Session):
        self.db = db

    def _require(self, row: Row | None, message: str) -> Row:
        if row is None:
            raise not_found(message)
        return row
