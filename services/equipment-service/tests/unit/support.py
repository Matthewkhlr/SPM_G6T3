from datetime import datetime

from app.dao.equipment_activity_log_dao import EquipmentActivityLogDAO
from app.dao.equipment_dao import EquipmentDAO
from app.dao.equipment_request_dao import EquipmentRequestDAO
from app.dao.equipment_reservation_dao import EquipmentReservationDAO
from app.dao.equipment_unit_dao import EquipmentUnitDAO
from app.models.equipment_unit import EquipmentUnit
from app.schemas.equipment import EquipmentCreate, OutOfServiceCounts
from app.services.equipment_service import EquipmentService
from shared.testing.cases import ServiceTestCase

CALLER = {"userId": "u-tech", "userName": "Cara", "role": "techsupport"}
COORDINATOR = {"userId": "u-coord", "userName": "Ben", "role": "coordinator"}
START = datetime(2026, 10, 6, 9, 0)
END = datetime(2026, 10, 6, 17, 0)


def equipment_create(**overrides):
    data = dict(
        code="PX-200",
        name="Projector",
        category="display",
        description="HDMI",
        totalQuantity=4,
        homeLocation="Store",
        technicalNotes="Spare lamp",
        outOfService=OutOfServiceCounts(),
    )
    data.update(overrides)
    return EquipmentCreate(**data)


class EquipmentCase(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.service = EquipmentService(
            self.db,
            EquipmentDAO(self.db),
            EquipmentUnitDAO(self.db),
            EquipmentActivityLogDAO(self.db),
            EquipmentReservationDAO(self.db),
            EquipmentRequestDAO(self.db),
        )

    def add_unit(self, equipment_id, status):
        self.db.add(EquipmentUnit(unitId=f"unit-{equipment_id}-{status}", equipmentId=equipment_id, status=status))
        self.db.commit()
