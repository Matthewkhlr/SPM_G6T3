"""SPM-46: only the coordinator assigned to an event can request equipment for
it or change its pending requests, and a reassignment moves that right."""

import unittest
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.clients import fetch_event_coordinator
from app.schemas.equipment import EquipmentRequestCreate
from app.services.equipment_service import require_assigned_coordinator
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, COORDINATOR, END, START, EquipmentCase, equipment_create

OTHER_COORDINATOR = {"userId": "u-other", "userName": "Cara", "role": "coordinator"}
HEADERS = {"Authorization": "Bearer token"}


def response(status_code, body=None):
    reply = MagicMock(status_code=status_code)
    reply.json.return_value = body
    return reply


class TestTheRule(unittest.TestCase):
    def test_the_assigned_coordinator_may_act(self):
        self.assertIsNone(require_assigned_coordinator("u-coord", "u-coord", "request equipment for it"))

    def test_any_other_coordinator_or_an_event_with_no_coordinator_is_refused_in_plain_words(self):
        for assigned in ("u-other", None, ""):
            with self.subTest(assigned=assigned), self.assertRaises(HTTPException) as ctx:
                require_assigned_coordinator(assigned, "u-coord", "request equipment for it")
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(
                ctx.exception.detail, "Only the coordinator assigned to this event can request equipment for it."
            )


class TestEventCoordinatorClient(unittest.TestCase):
    def test_reads_the_events_current_coordinator_forwarding_the_callers_token(self):
        with patch("app.orchestration.clients.httpx.get", return_value=response(200, {"coordinatorId": "u2"})) as get:
            self.assertEqual(fetch_event_coordinator("e1", "Bearer t"), "u2")
        self.assertTrue(get.call_args.args[0].endswith("/events/e1"))
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer t"})

    def test_an_event_with_no_coordinator_gives_none(self):
        with patch("app.orchestration.clients.httpx.get", return_value=response(200, {"coordinatorId": None})):
            self.assertIsNone(fetch_event_coordinator("e1", "Bearer t"))

    def test_an_unknown_event_is_not_found(self):
        with patch("app.orchestration.clients.httpx.get", return_value=response(404)), self.assertRaises(
            HTTPException
        ) as ctx:
            fetch_event_coordinator("nope", "Bearer t")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Event not found")

    def test_event_service_errors_and_outages_are_reported_in_plain_words(self):
        for failure in (
            patch("app.orchestration.clients.httpx.get", return_value=response(500)),
            patch("app.orchestration.clients.httpx.get", side_effect=httpx.ConnectError("refused")),
        ):
            with self.subTest(failure=failure), failure, self.assertRaises(HTTPException) as ctx:
                fetch_event_coordinator("e1", "Bearer t")
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertEqual(
                ctx.exception.detail, "The event's details could not be loaded right now. Please try again shortly."
            )


class TestAssignedCoordinatorRoutes(EquipmentCase):
    """The event is assigned to COORDINATOR unless a test reassigns it."""

    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.signed_in = patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR)
        self.assigned = patch("app.routers.equipment.fetch_event_coordinator", return_value=COORDINATOR["userId"])
        self.caller = self.signed_in.start()
        self.event_coordinator = self.assigned.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.equipment_id = self.service.create_equipment(equipment_create(), CALLER).equipmentId

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.assigned.stop()
        self.signed_in.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def sign_in_as(self, caller):
        self.caller.return_value = caller

    def reassign_to(self, coordinator):
        self.event_coordinator.return_value = coordinator["userId"]

    def request_equipment(self, event_id="e1"):
        return self.client.post(
            "/equipment/requests",
            headers=HEADERS,
            json={
                "eventId": event_id,
                "equipmentId": self.equipment_id,
                "quantity": 1,
                "startsAt": START.isoformat(),
                "endsAt": END.isoformat(),
            },
        )

    def refine(self, request_id, quantity=2):
        return self.client.patch(
            f"/equipment/requests/{request_id}/details", headers=HEADERS, json={"quantity": quantity}
        )

    def pending_request(self, event_id="e7"):
        return self.service.create_request(
            EquipmentRequestCreate(
                eventId=event_id, equipmentId=self.equipment_id, quantity=1, startsAt=START, endsAt=END
            ),
            COORDINATOR["userId"],
        )

    def test_the_assigned_coordinator_can_request_equipment(self):
        created = self.request_equipment()

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["requestedBy"], COORDINATOR["userId"])
        self.event_coordinator.assert_called_once_with("e1", HEADERS["Authorization"])

    def test_a_coordinator_not_assigned_to_the_event_cannot_request_equipment_and_nothing_is_saved(self):
        self.sign_in_as(OTHER_COORDINATOR)

        refused = self.request_equipment()

        self.assertEqual(refused.status_code, 403)
        self.assertEqual(
            refused.json()["detail"], "Only the coordinator assigned to this event can request equipment for it."
        )
        self.assertEqual(self.service.list_requests(), [])

    def test_an_event_with_no_coordinator_yet_cannot_have_equipment_requested(self):
        self.event_coordinator.return_value = None

        self.assertEqual(self.request_equipment().status_code, 403)
        self.assertEqual(self.service.list_requests(), [])

    def test_the_assigned_coordinator_can_change_a_pending_request(self):
        request = self.pending_request()

        refined = self.refine(request.requestId, quantity=3)

        self.assertEqual(refined.status_code, 200)
        self.assertEqual(refined.json()["quantity"], 3)
        # The request's own event is checked, not some other event.
        self.event_coordinator.assert_called_once_with("e7", HEADERS["Authorization"])

    def test_a_coordinator_not_assigned_to_the_event_cannot_change_its_requests(self):
        request = self.pending_request()
        self.sign_in_as(OTHER_COORDINATOR)

        refused = self.refine(request.requestId, quantity=3)

        self.assertEqual(refused.status_code, 403)
        self.assertEqual(
            refused.json()["detail"], "Only the coordinator assigned to this event can change its equipment requests."
        )
        self.assertEqual(self.service.get_request(request.requestId).quantity, 1)

    def test_changing_an_unknown_request_is_not_found_without_asking_event_service(self):
        self.assertEqual(self.refine("nope").status_code, 404)
        self.event_coordinator.assert_not_called()

    def test_reassignment_takes_the_right_from_the_previous_coordinator_and_gives_it_to_the_new_one(self):
        """AC3: nobody signs out; the next request is judged by the event's coordinator at that moment."""
        request = self.pending_request()
        self.reassign_to(OTHER_COORDINATOR)

        previous_request = self.request_equipment()
        previous_change = self.refine(request.requestId)
        self.sign_in_as(OTHER_COORDINATOR)
        new_request = self.request_equipment()
        new_change = self.refine(request.requestId, quantity=4)

        self.assertEqual((previous_request.status_code, previous_change.status_code), (403, 403))
        self.assertEqual((new_request.status_code, new_change.status_code), (201, 200))
        self.assertEqual(new_change.json()["quantity"], 4)
