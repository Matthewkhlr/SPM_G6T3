import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — registers every model on Base.metadata
from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_dao import EventDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.db.session import Base
from app.services.event_service import EventService


@pytest.fixture()
def db_session(monkeypatch):
    # No registration-service running in tests; _to_out() calls registration_count()
    # for every event it returns, so stub it instead of hitting the network.
    monkeypatch.setattr(
        "app.services.event_service.registration_count", lambda event_id, authorization=None: 0
    )

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def event_service(db_session):
    return EventService(
        db_session,
        EventDAO(db_session),
        EventAssignmentDAO(db_session),
        EventStatusHistoryDAO(db_session),
    )
