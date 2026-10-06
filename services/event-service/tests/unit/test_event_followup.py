from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.event_change_request import EventChangeRequest
from app.schemas.followup import ReadinessCreate, ReadinessPatch
from app.orchestration.clients import release_event_holds
from app.schemas.event import OrganiserDraftPatch
from app.services.event_followup import EventFollowUp, _equipment_status, _person, _soft_get
from pydantic import ValidationError
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import COORDINATOR, EventCase, insert_event


NOW = datetime.utcnow()


def _open_event(db, **overrides):
    data = dict(
        eventId="e-open",
        status="confirmed",
        eventName="AI in Events Summit",
        category="conference",
        registrationEnabled=True,
        registrationOpensAt=NOW - timedelta(days=2),
        registrationClosesAt=NOW + timedelta(days=5),
        capacity=5,
        proposedStartAt=NOW + timedelta(days=10),
        proposedEndAt=NOW + timedelta(days=10, hours=4),
        accessibilityNeeds="Wheelchair accessible",
        layoutPreference="Theatre",
        description="A public summit",
        coordinatorId="coord-1",
    )
    data.update(overrides)
    return insert_event(db, **data)


class TestFollowUp(EventCase):
    def setUp(self):
        super().setUp()
        self.follow = EventFollowUp(self.db)
        self.users = patch(
            "app.services.event_followup.list_users",
            return_value=[{"userId": "u3", "name": "Ben Lee", "email": "ben@example.com", "phone": "+65"}],
        )
        self.users.start()
        self.count = patch("app.services.event_followup.registration_count", return_value=1)
        self.count_mock = self.count.start()

    def tearDown(self):
        self.count.stop()
        self.users.stop()
        super().tearDown()

    def test_readiness_lines_can_be_created_updated_and_removed(self):
        _open_event(self.db)
        created = self.follow.create_item(
            "e-open",
            ReadinessCreate(
                category="registration",
                handlerId="u3",
                status="outstanding",
                note="AUTO-persist",
                dueAt=datetime.now(timezone.utc) + timedelta(days=2),
                attachments=[{"name": "Plan", "url": "https://example.test/plan"}],
            ),
            "Bearer token",
        )
        self.assertTrue(created.dueSoon)
        self.assertEqual(created.handlerName, "Ben Lee")
        self.assertEqual(created.attachments[0]["url"], "https://example.test/plan")
        read = self.follow.get_item("e-open", created.itemId)
        self.assertEqual(read.note, "AUTO-persist")
        updated = self.follow.update_item(
            "e-open",
            created.itemId,
            ReadinessPatch(
                note="AUTO-persist-edited",
                status="in_progress",
                handlerId="u9",
                category="safety",
                dueAt=datetime.utcnow() + timedelta(days=1),
                attachments=[{"name": "Note", "url": "https://example.test/note"}],
            ),
            "Bearer token",
        )
        self.assertIn("edited", updated.note)
        self.assertEqual(updated.handlerName, "u9")
        overdue = self.follow.create_item(
            "e-open",
            ReadinessCreate(
                category="equipment",
                handlerId="u3",
                dueAt=datetime.utcnow() - timedelta(days=2),
            ),
            "Bearer token",
        )
        self.assertTrue(overdue.overdue)
        self.assertFalse(overdue.dueSoon)
        alerts = self.follow.list_readiness("e-open", "Bearer token", due_soon=True)
        self.assertIn(created.itemId, [row.itemId for row in alerts])
        self.assertNotIn(overdue.itemId, [row.itemId for row in alerts])
        self.follow.delete_item("e-open", created.itemId)
        with self.assertRaises(HTTPException):
            self.follow.get_item("e-open", created.itemId)
        with self.assertRaises(HTTPException):
            self.follow.delete_item("e-open", created.itemId)
        with self.assertRaises(HTTPException):
            self.follow.update_item("e-open", "missing", ReadinessPatch(note="x"), "Bearer token")

    def test_derived_rows_reflect_equipment_and_can_be_confirmed(self):
        _open_event(self.db)
        with patch("app.services.event_followup._soft_get", return_value={"venueName": "Marina Hall A", "location": "HarbourFront Centre"}):
            rows = self.follow.list_readiness("e-open", None)
        self.assertEqual(rows[0].category, "venue")
        self.assertEqual(rows[0].status, "in place")
        self.assertTrue(rows[0].attachments)
        self.assertIn("@", rows[0].handlerEmail)
        confirmed = self.follow.update_item(
            "e-open", "derived-venue", ReadinessPatch(status="confirmed"), None
        )
        self.assertEqual(confirmed.status, "confirmed")
        again = self.follow.list_readiness("e-open", None)
        self.assertEqual(sum(1 for row in again if row.itemId == "derived-venue"), 1)

    def test_equipment_requests_that_are_not_a_list_are_ignored(self):
        _open_event(self.db)

        def answers(url, authorization, params=None):
            if url.endswith("/requests"):
                return {"unexpected": True}
            if "reservations" in url:
                return [{"eventId": "e-open", "status": "active", "quantity": 1}]
            return {}

        with patch("app.services.event_followup._soft_get", side_effect=answers):
            rows = self.follow.list_readiness("e-open", "Bearer token")
        equipment = next(row for row in rows if row.category == "equipment")
        self.assertEqual(equipment.status, "ready")

    def test_open_events_exclude_closed_windows_and_keep_a_change_timestamp(self):
        _open_event(self.db)
        _open_event(
            self.db,
            eventId="e-later",
            eventName="Later",
            registrationOpensAt=NOW + timedelta(days=3),
        )
        _open_event(self.db, eventId="e-shut", eventName="Shut", registrationEnabled=False)
        _open_event(
            self.db,
            eventId="e-ended",
            eventName="Ended",
            registrationClosesAt=NOW - timedelta(days=1),
        )
        _open_event(self.db, eventId="e-plan", eventName="Plan", status="planning")
        self.db.add(
            EventChangeRequest(
                changeRequestId="cr1",
                eventId="e-open",
                requestedBy="org-1",
                status="applied",
                proposedChanges={"proposedStartAt": "2026-12-01T09:00:00"},
                reviewedAt=NOW,
                createdAt=NOW - timedelta(days=1),
            )
        )
        self.db.add(
            EventChangeRequest(
                changeRequestId="cr2",
                eventId="e-open",
                requestedBy="org-1",
                status="pending",
                proposedChanges={"proposedStartAt": "2026-12-02T09:00:00"},
                createdAt=NOW,
            )
        )
        self.db.add(
            EventChangeRequest(
                changeRequestId="cr3",
                eventId="e-open",
                requestedBy="org-1",
                status="applied",
                proposedChanges={"purpose": "unchanged date"},
                createdAt=NOW,
            )
        )
        self.db.commit()
        with patch("app.services.event_followup._soft_get", return_value={"venueName": "Marina Hall A", "location": "HarbourFront Centre"}):
            listed = self.follow.list_open("Bearer token")
        ids = [row.eventId for row in listed]
        self.assertEqual(ids, ["e-open"])
        self.assertEqual(listed[0].venueName, "Marina Hall A")
        self.assertIsNotNone(listed[0].changedAt)
        self.assertFalse(listed[0].full)
        self.count_mock.return_value = 5
        with patch("app.services.event_followup._soft_get", return_value={}):
            full = self.follow.get_open("e-open", "Bearer token")
        self.assertTrue(full.full)
        self.assertEqual(full.remaining, 0)
        with self.assertRaises(HTTPException):
            self.follow.get_open("e-later", "Bearer token")
        self.assertEqual(self.follow.list_open("Bearer token", search="zzzz"), [])
        narrowed = self.follow.list_open("Bearer token", search="AI", category="workshop")
        self.assertEqual(narrowed, [])
        dated = self.follow.list_open("Bearer token", from_date=(NOW + timedelta(days=30)).date().isoformat())
        self.assertEqual(dated, [])
        card = self.follow.attendee_card("e-open", None)
        self.assertEqual(card.eventName, "AI in Events Summit")
        with self.assertRaises(HTTPException):
            self.follow.attendee_card("missing", None)

    def test_equipment_status_and_person_lookup(self):
        self.assertEqual(_equipment_status([{"status": "complete", "quantity": 1, "reviewNote": ""}], []), "ready")
        self.assertEqual(
            _equipment_status(
                [{"status": "pending", "quantity": 2, "reviewNote": ""}],
                [{"status": "active", "quantity": 2}],
            ),
            "ready",
        )
        self.assertEqual(_equipment_status([], [{"status": "active", "quantity": 1}]), "ready")
        self.assertEqual(
            _equipment_status(
                [{"status": "partial", "quantity": 2, "reviewNote": ""}],
                [{"status": "partial", "quantity": 1}],
            ),
            "needs attention",
        )
        self.assertEqual(
            _equipment_status(
                [{"status": "rejected", "quantity": 2, "reviewNote": "Reserved from the catalogue quantity check"}],
                [{"status": "released", "quantity": 1}],
            ),
            "needs attention",
        )
        self.assertEqual(_equipment_status([], []), "outstanding")
        self.assertEqual(_person("u3", "Bearer token"), ("Ben Lee", "ben@example.com", "+65"))
        self.assertEqual(_person("missing", "Bearer token"), ("", "", ""))
        with patch("app.services.event_followup.list_users", side_effect=RuntimeError("down")):
            self.assertEqual(_person("u3", "Bearer token"), ("", "", ""))

    def test_soft_get_swallows_failures(self):
        self.assertIsNone(_soft_get("http://example.test", None))
        failed = MagicMock(status_code=503)
        with patch("app.services.event_followup.httpx.get", return_value=failed):
            self.assertIsNone(_soft_get("http://example.test", "Bearer token"))
        ok = MagicMock(status_code=200)
        ok.json.return_value = {"ok": True}
        with patch("app.services.event_followup.httpx.get", return_value=ok):
            self.assertEqual(_soft_get("http://example.test", "Bearer token", {"eventId": "e1"}), {"ok": True})
        with patch("app.services.event_followup.httpx.get", side_effect=httpx.HTTPError("down")):
            self.assertIsNone(_soft_get("http://example.test", "Bearer token"))
        with self.assertRaises(ValidationError):
            OrganiserDraftPatch(proposedStartAt=NOW + timedelta(days=2), proposedEndAt=NOW)
        draft = _open_event(self.db, eventId="e-blank", status="draft", eventName="Named")
        draft.eventName = ""
        self.db.commit()
        with self.assertRaises(HTTPException):
            self.service.submit_stored_draft("e-blank", "org-1")
        with patch("app.orchestration.clients.httpx.Client") as client:
            client.return_value.__enter__.return_value.post.side_effect = httpx.HTTPError("down")
            release_event_holds("e1", "Bearer token")
        with patch("app.orchestration.clients.httpx.Client") as client:
            client.return_value.__enter__.return_value.post.return_value = MagicMock()
            release_event_holds("e1", None)


class TestFollowUpRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.event.resolve_caller", return_value=COORDINATOR)
        self.caller.start()
        self.count = patch("app.services.event_followup.registration_count", return_value=0)
        self.count.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.count.stop()
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_readiness_and_open_routes(self):
        _open_event(self.db, eventId="e-route", registrationEnabled=True)
        created = self.client.post(
            "/events/e-route/readiness-items",
            headers=self.headers,
            json={"category": "venue", "handlerId": "u3", "status": "outstanding", "note": "AUTO"},
        )
        self.assertEqual(created.status_code, 201)
        item_id = created.json()["itemId"]
        self.assertEqual(self.client.get(f"/events/e-route/readiness-items/{item_id}", headers=self.headers).status_code, 200)
        patched = self.client.patch(
            f"/events/e-route/readiness-items/{item_id}",
            headers=self.headers,
            json={"note": "edited"},
        )
        self.assertEqual(patched.status_code, 200)
        listed = self.client.get("/events/e-route/readiness", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertGreaterEqual(len(listed.json()), 1)
        removed = self.client.delete(f"/events/e-route/readiness-items/{item_id}", headers=self.headers)
        self.assertEqual(removed.status_code, 204)
        opened = self.client.get("/events/open-for-registration", headers=self.headers)
        self.assertEqual(opened.status_code, 200)
        one = self.client.get("/events/open-for-registration/e-route", headers=self.headers)
        self.assertEqual(one.status_code, 200)
        card = self.client.get("/events/e-route/attendee-card", headers=self.headers)
        self.assertEqual(card.status_code, 200)
        self.assertNotIn("internalNotes", card.json())
