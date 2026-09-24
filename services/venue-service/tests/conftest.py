import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — registers every model on Base.metadata
from app.dao.venue_activity_log_dao import VenueActivityLogDAO
from app.dao.venue_booking_dao import VenueBookingDAO
from app.dao.venue_dao import VenueDAO
from app.db.session import Base
from app.services.venue_service import VenueService


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
def venue_service(db_session):
    return VenueService(
        db_session,
        VenueDAO(db_session),
        VenueActivityLogDAO(db_session),
        VenueBookingDAO(db_session),
    )
