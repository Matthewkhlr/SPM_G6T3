from fastapi import HTTPException

from app.schemas.equipment import EquipmentRequestCreate
from tests.unit.support import CALLER, END, START, EquipmentCase, equipment_create


class TestEquipmentRequests(EquipmentCase):
    def test_request_review_and_reserve(self):
        created = self.service.create_equipment(equipment_create(code="REQ"), CALLER)
        request = self.service.create_request(
            EquipmentRequestCreate(
                eventId="e1",
                equipmentId=created.equipmentId,
                quantity=1,
                technicalRequirements="HDMI",
                startsAt=START,
                endsAt=END,
            ),
            "u-coord",
        )
        self.assertEqual(request.status, "pending")

        rejected = self.service.review_request(request.requestId, "u-tech", False, "No stock")
        self.assertEqual(rejected.status, "rejected")
        with self.assertRaises(HTTPException) as ctx:
            self.service.review_request(request.requestId, "u-tech", True, "Again")
        self.assertEqual(ctx.exception.status_code, 409)
        with self.assertRaises(HTTPException) as ctx:
            self.service.reserve_request(request.requestId)
        self.assertEqual(ctx.exception.status_code, 409)

        pending = self.service.create_request(
            EquipmentRequestCreate(eventId="e2", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END),
            "u-coord",
        )
        approved = self.service.review_request(pending.requestId, "u-tech", True, "OK")
        self.assertEqual(approved.status, "approved")
        reserved = self.service.reserve_request(pending.requestId)
        self.assertEqual(reserved.status, "active")
        self.assertEqual(reserved.eventId, "e2")
        with self.assertRaises(HTTPException) as ctx:
            self.service.reserve_request(pending.requestId)
        self.assertEqual(ctx.exception.status_code, 409)
