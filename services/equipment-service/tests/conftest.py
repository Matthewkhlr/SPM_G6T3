import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — registers every model on Base.metadata
from app.dao.equipment_activity_log_dao import EquipmentActivityLogDAO
from app.dao.equipment_dao import EquipmentDAO
from app.dao.equipment_request_dao import EquipmentRequestDAO
from app.dao.equipment_reservation_dao import EquipmentReservationDAO
from app.dao.equipment_unit_dao import EquipmentUnitDAO
from app.db.session import Base
from app.services.equipment_service import EquipmentService


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
def equipment_service(db_session):
    return EquipmentService(
        db_session,
        EquipmentDAO(db_session),
        EquipmentUnitDAO(db_session),
        EquipmentActivityLogDAO(db_session),
        EquipmentReservationDAO(db_session),
        EquipmentRequestDAO(db_session),
    )
