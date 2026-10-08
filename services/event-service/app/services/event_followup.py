"""SPM-5 readiness lines, and the public event card used by browse and registration."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

from app.core.config import settings
from app.dao.event_change_request_dao import EventChangeRequestDAO
from app.dao.event_dao import EventDAO
from app.dao.event_readiness_dao import EventReadinessDAO
from app.models.event import Event
from app.models.event_readiness import EventReadinessItem
from app.orchestration.clients import list_users, registration_count
from app.schemas.followup import OpenEventOut, ReadinessCreate, ReadinessItemOut, ReadinessPatch
from app.services.arrangements import equipment_status as _equipment_status
from shared.exceptions.http import not_found
from shared.services.base import BaseService

DUE_SOON = timedelta(days=3)
DATE_FIELDS = {"proposedStartAt", "proposedEndAt", "layoutPreference"}


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _soft_get(url: str, authorization: str | None, params: dict | None = None):
    if not authorization:
        return None
    try:
        response = httpx.get(
            url, headers={"Authorization": authorization}, params=params or None, timeout=0.8
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    return response.json()


def _person(user_id: str, authorization: str | None) -> tuple[str, str, str]:
    try:
        users = list_users(authorization)
    except Exception:
        return "", "", ""
    for user in users:
        if user.get("userId") == user_id:
            return user.get("name") or "", user.get("email") or "", user.get("phone") or ""
    return "", "", ""


def _flags(due_at: datetime | None, now: datetime) -> tuple[bool, bool]:
    if due_at is None:
        return False, False
    due = _naive(due_at)
    if due < now:
        return False, True
    return due - now <= DUE_SOON, False


def _item_out(row: EventReadinessItem, now: datetime) -> ReadinessItemOut:
    due_soon, overdue = _flags(row.dueAt, now)
    name = row.handlerName or row.handlerId
    return ReadinessItemOut(
        itemId=row.itemId,
        eventId=row.eventId,
        category=row.category,
        handlerId=row.handlerId,
        handlerName=name,
        personnel=name,
        handlerEmail=row.handlerEmail or "",
        handlerPhone=row.handlerPhone or "",
        status=row.status,
        note=row.note or "",
        assignedAt=row.assignedAt,
        dueAt=row.dueAt,
        dueSoon=due_soon,
        alert=due_soon or overdue,
        overdue=overdue,
        attachments=list(row.attachments or []),
    )


class EventFollowUp(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.events = EventDAO(db)
        self.readiness = EventReadinessDAO(db)
        self.changes = EventChangeRequestDAO(db)

    def _event(self, event_id: str) -> Event:
        row = self.events.get_by_id(event_id)
        if row is None:
            raise not_found("Event not found")
        return row

    def _derived(self, event: Event, authorization: str | None, now: datetime) -> list[ReadinessItemOut]:
        name, email, phone = _person(event.coordinatorId or "", authorization)
        if not name:
            name = "Event coordinator"
        if not email and not phone:
            email = "coordinator@connectsphere.local"
        requests = _soft_get(
            f"{settings.equipment_service_url}/equipment/requests", authorization
        ) or []
        reservations = _soft_get(
            f"{settings.equipment_service_url}/equipment/reservations",
            authorization,
            {"eventId": event.eventId},
        ) or []
        if isinstance(requests, dict):
            requests = []
        requests = [row for row in requests if row.get("eventId") == event.eventId]
        bookings = _soft_get(
            f"{settings.venue_service_url}/venues/bookings/public-summary",
            authorization,
            {"eventId": event.eventId},
        ) or {}
        venue_status = "in place" if bookings.get("venueName") else "outstanding"
        assigned = event.updatedAt or event.createdAt or now
        venue = ReadinessItemOut(
            itemId="derived-venue",
            eventId=event.eventId,
            category="venue",
            handlerId=event.coordinatorId or "",
            handlerName=name,
            personnel=name,
            handlerEmail=email,
            handlerPhone=phone,
            status=venue_status,
            assignedAt=assigned,
            attachments=[{"name": "Arrangement summary", "url": f"/app/events/{event.eventId}"}],
        )
        equipment = venue.model_copy(
            update={
                "itemId": "derived-equipment",
                "category": "equipment",
                "status": _equipment_status(requests, reservations if isinstance(reservations, list) else []),
                "attachments": [],
            }
        )
        stored = {row.itemId for row in self.readiness.list_for_event(event.eventId)}
        return [row for row in (venue, equipment) if row.itemId not in stored]

    def list_readiness(self, event_id: str, authorization: str | None, due_soon: bool = False) -> list[ReadinessItemOut]:
        event = self._event(event_id)
        now = datetime.utcnow()
        rows = [_item_out(row, now) for row in self.readiness.list_for_event(event_id)]
        rows.extend(self._derived(event, authorization, now))
        if due_soon:
            return [row for row in rows if row.dueSoon]
        return rows

    def get_item(self, event_id: str, item_id: str) -> ReadinessItemOut:
        self._event(event_id)
        row = self.readiness.get(item_id)
        if row is None or row.eventId != event_id:
            raise not_found("Readiness item not found")
        return _item_out(row, datetime.utcnow())

    def create_item(self, event_id: str, body: ReadinessCreate, authorization: str | None) -> ReadinessItemOut:
        self._event(event_id)
        name, email, phone = _person(body.handlerId, authorization)
        row = EventReadinessItem(
            itemId=str(uuid4()),
            eventId=event_id,
            category=body.category,
            handlerId=body.handlerId,
            handlerName=name or body.handlerId,
            handlerEmail=email,
            handlerPhone=phone,
            status=body.status,
            note=body.note,
            dueAt=_naive(body.dueAt),
            assignedAt=datetime.utcnow(),
            attachments=[item.model_dump() for item in body.attachments],
        )
        self.readiness.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _item_out(row, datetime.utcnow())

    def update_item(self, event_id: str, item_id: str, body: ReadinessPatch, authorization: str | None) -> ReadinessItemOut:
        event = self._event(event_id)
        row = self.readiness.get(item_id)
        if row is None and item_id in ("derived-venue", "derived-equipment"):
            derived = {item.itemId: item for item in self._derived(event, authorization, datetime.utcnow())}
            current = derived[item_id]
            row = EventReadinessItem(
                itemId=item_id,
                eventId=event_id,
                category=current.category,
                handlerId=current.handlerId,
                handlerName=current.handlerName,
                handlerEmail=current.handlerEmail,
                handlerPhone=current.handlerPhone,
                status=current.status,
                note=current.note,
                assignedAt=current.assignedAt,
                attachments=current.attachments,
            )
            self.readiness.add(row)
        if row is None or row.eventId != event_id:
            raise not_found("Readiness item not found")
        sent = body.model_fields_set
        if "category" in sent and body.category is not None:
            row.category = body.category
        if "status" in sent and body.status is not None:
            row.status = body.status
        if "note" in sent and body.note is not None:
            row.note = body.note
        if "dueAt" in sent:
            row.dueAt = _naive(body.dueAt)
        if "handlerId" in sent and body.handlerId is not None:
            name, email, phone = _person(body.handlerId, authorization)
            row.handlerId = body.handlerId
            row.handlerName = name or body.handlerId
            row.handlerEmail = email
            row.handlerPhone = phone
        if "attachments" in sent and body.attachments is not None:
            row.attachments = [item.model_dump() for item in body.attachments]
        self.db.commit()
        self.db.refresh(row)
        return _item_out(row, datetime.utcnow())

    def delete_item(self, event_id: str, item_id: str) -> None:
        self._event(event_id)
        row = self.readiness.get(item_id)
        if row is None or row.eventId != event_id:
            raise not_found("Readiness item not found")
        self.db.delete(row)
        self.db.commit()

    def _changed_at(self, event_id: str) -> datetime | None:
        moments = []
        for change in self.changes.list_by_event(event_id):
            if change.status not in ("accepted", "applied"):
                continue
            proposed = change.proposedChanges or {}
            if not (DATE_FIELDS & set(proposed)):
                continue
            moments.append(change.reviewedAt or change.createdAt)
        return max(moments) if moments else None

    def _card(self, event: Event, authorization: str | None) -> OpenEventOut:
        count = registration_count(event.eventId, authorization)
        remaining = max((event.capacity or 0) - count, 0)
        venue = _soft_get(
            f"{settings.venue_service_url}/venues/bookings/public-summary",
            authorization,
            {"eventId": event.eventId},
        ) or {}
        return OpenEventOut(
            eventId=event.eventId,
            eventName=event.eventName,
            status=event.status,
            category=event.category,
            description=event.description or "",
            purpose=event.purpose or "",
            proposedStartAt=event.proposedStartAt,
            proposedEndAt=event.proposedEndAt,
            startsAt=event.proposedStartAt,
            endsAt=event.proposedEndAt,
            accessibilityNeeds=event.accessibilityNeeds or "",
            layoutPreference=event.layoutPreference,
            registrationClosesAt=event.registrationClosesAt,
            capacity=event.capacity or 0,
            registeredCount=count,
            remaining=remaining,
            full=remaining == 0 and (event.capacity or 0) > 0,
            venueName=venue.get("venueName") or "",
            venueLocation=venue.get("location") or "",
            changedAt=self._changed_at(event.eventId),
        )

    def _open(self, event: Event, now: datetime) -> bool:
        if event.status != "confirmed" or not event.registrationEnabled:
            return False
        if event.registrationOpensAt and event.registrationOpensAt > now:
            return False
        if event.registrationClosesAt and event.registrationClosesAt < now:
            return False
        return True

    def list_open(self, authorization: str | None, search: str = "", category: str = "", from_date: str = "") -> list[OpenEventOut]:
        now = datetime.utcnow()
        rows = []
        for event in self.events.list_by_status("confirmed"):
            if not self._open(event, now):
                continue
            if search and search.lower() not in (event.eventName or "").lower():
                continue
            if category and (event.category or "").lower() != category.lower():
                continue
            if from_date and event.proposedStartAt and event.proposedStartAt.date().isoformat() < from_date:
                continue
            rows.append(self._card(event, authorization))
        return rows

    def get_open(self, event_id: str, authorization: str | None) -> OpenEventOut:
        event = self._event(event_id)
        if not self._open(event, datetime.utcnow()):
            raise not_found("This event is not open for registration")
        return self._card(event, authorization)

    def attendee_card(self, event_id: str, authorization: str | None) -> OpenEventOut:
        return self._card(self._event(event_id), authorization)
