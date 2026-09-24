import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — registers every model on Base.metadata
from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.db.session import Base
from app.services.registration_service import RegistrationService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def registration_service(db_session):
    return RegistrationService(db_session, AttendeeRegistrationDAO(db_session), RegistrationWindowDAO(db_session))
