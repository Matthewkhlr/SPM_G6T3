import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — registers every model on Base.metadata
from app.db.session import Base


@pytest.fixture()
def db_session(monkeypatch):
    # No registration-service running in tests; _to_out() calls registration_count()
    # for every event it returns, so stub it instead of hitting the network.
    monkeypatch.setattr("app.services.event_service.registration_count", lambda event_id: 0)

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
