from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.models.equipment_reservation import EquipmentReservation
from app.schemas.equipment import EquipmentRequestCreate
from tests.unit.support import CALLER, END, START, EquipmentCase, equipment_create


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class _Client:
    get_result = _Response(200, [])
    fail_post = False
    posted = None

    def __init__(self, timeout=5):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        if isinstance(_Client.get_result, Exception):
            raise _Client.get_result
        return _Client.get_result

    def post(self, url, headers=None, json=None):
        if _Client.fail_post:
            raise httpx.ConnectError("down")
        _Client.posted = json
        return _Response(200, {"status": "queued"})


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
        self.assertEqual(self.service.get_request(pending.requestId).status, "reserved")
        with self.assertRaises(HTTPException) as ctx:
            self.service.reserve_request(pending.requestId)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIsNotNone(approved.reviewedAt)
        self.assertEqual(approved.reviewedBy, "u-tech")

        held = self.service.create_request(
            EquipmentRequestCreate(eventId="e3", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END),
            "u-coord",
        )
        self.service.review_request(held.requestId, "u-tech", True, "OK")
        self.db.add(
            EquipmentReservation(
                reservationId=str(uuid4()),
                requestId=held.requestId,
                eventId="e3",
                equipmentId=created.equipmentId,
                quantity=1,
                startsAt=START,
                endsAt=END,
                status="active",
            )
        )
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            self.service.reserve_request(held.requestId)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("already reserved", ctx.exception.detail)

    def test_coordinator_can_refine_a_pending_request_only(self):
        created = self.service.create_equipment(equipment_create(code="REFINE"), CALLER)
        request = self._request(created, "e-refine")
        refined = self.service.refine_request(request.requestId, 4, "Need a longer HDMI run")
        self.assertEqual(refined.quantity, 4)
        self.assertEqual(refined.technicalRequirements, "Need a longer HDMI run")
        self.assertEqual(refined.status, "pending")
        self.assertIsNone(refined.reviewedBy)

        approved = self.service.review_request(request.requestId, "u-tech", True, "OK")
        with self.assertRaises(HTTPException) as ctx:
            self.service.refine_request(approved.requestId, 1, None)
        self.assertEqual(ctx.exception.status_code, 409)
        with self.assertRaises(HTTPException) as missing:
            self.service.refine_request("missing", 1, "note")
        self.assertEqual(missing.exception.status_code, 404)

        pending = self._request(created, "e-refine-blank")
        with self.assertRaises(HTTPException) as blank_reason:
            self.service.mark_unavailable(pending.requestId, CALLER, "   ", "", None)
        self.assertEqual(blank_reason.exception.status_code, 422)
        self.assertEqual(self.service.get_request(pending.requestId).status, "pending")
        with self.assertRaises(HTTPException) as blank_reject:
            self.service.review_request(pending.requestId, "u-tech", False, "  ")
        self.assertEqual(blank_reject.exception.status_code, 422)
        self.assertEqual(self.service.get_request(pending.requestId).status, "pending")

    def _request(self, created, event_id):
        return self.service.create_request(
            EquipmentRequestCreate(eventId=event_id, equipmentId=created.equipmentId, quantity=2, startsAt=START, endsAt=END),
            "u-coord",
        )

    def test_unavailable_records_who_and_when_and_queues_email(self):
        created = self.service.create_equipment(equipment_create(code="UNAV"), CALLER)
        request = self._request(created, "e-unav")
        _Client.get_result = _Response(200, [{"userId": "u-coord", "email": "coordinator@connectsphere.com"}])
        _Client.fail_post = False
        _Client.posted = None

        with patch("app.services.equipment_service.httpx.Client", _Client):
            marked = self.service.mark_unavailable(
                request.requestId, CALLER, "insufficient stock", "Only two exist", "Bearer token"
            )

        self.assertEqual(marked.status, "unavailable")
        self.assertEqual(marked.reviewedBy, "u-tech")
        self.assertIsNotNone(marked.reviewedAt)
        self.assertIn("insufficient stock", marked.reviewNote)
        self.assertEqual(_Client.posted["to"], "coordinator@connectsphere.com")
        opened = self.service.get_request(request.requestId)
        self.assertEqual(opened.status, "unavailable")

        with self.assertRaises(HTTPException) as ctx:
            self.service.mark_unavailable(request.requestId, CALLER, "again", "", "Bearer token")
        self.assertEqual(ctx.exception.status_code, 409)

        with self.assertRaises(HTTPException) as ctx:
            self.service.get_request("missing")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_unavailable_still_saves_when_the_email_cannot_be_queued(self):
        created = self.service.create_equipment(equipment_create(code="MAIL"), CALLER)
        silent = self._request(created, "e-silent")
        marked = self.service.mark_unavailable(silent.requestId, CALLER, "no stock", "", None)
        self.assertEqual(marked.status, "unavailable")
        self.assertEqual(marked.reviewNote, "no stock")

        refused = self._request(created, "e-down")
        _Client.get_result = httpx.ConnectError("down")
        with patch("app.services.equipment_service.httpx.Client", _Client):
            marked = self.service.mark_unavailable(refused.requestId, CALLER, "no stock", "", "Bearer token")
        self.assertEqual(marked.status, "unavailable")

        missing = self._request(created, "e-miss")
        _Client.get_result = _Response(503, [])
        with patch("app.services.equipment_service.httpx.Client", _Client):
            marked = self.service.mark_unavailable(missing.requestId, CALLER, "no stock", "", "Bearer token")
        self.assertEqual(marked.status, "unavailable")

        blank = self._request(created, "e-blank")
        _Client.get_result = _Response(200, [{"userId": "other", "email": "other@connectsphere.com"}])
        _Client.fail_post = False
        _Client.posted = None
        with patch("app.services.equipment_service.httpx.Client", _Client):
            marked = self.service.mark_unavailable(blank.requestId, CALLER, "no stock", "", "Bearer token")
        self.assertIsNone(_Client.posted)
        self.assertEqual(marked.reviewedBy, "u-tech")

        queued_fail = self._request(created, "e-post")
        _Client.get_result = _Response(200, [{"userId": "u-coord", "email": "coordinator@connectsphere.com"}])
        _Client.fail_post = True
        with patch("app.services.equipment_service.httpx.Client", _Client):
            marked = self.service.mark_unavailable(queued_fail.requestId, CALLER, "no stock", "later", "Bearer token")
        self.assertEqual(marked.status, "unavailable")
