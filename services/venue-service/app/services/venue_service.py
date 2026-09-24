import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.dao.venue_activity_log_dao import VenueActivityLogDAO
from app.dao.venue_booking_dao import VenueBookingDAO
from app.dao.venue_dao import VenueDAO
from app.models.venue_booking import VenueBooking
from app.models.venue_info import VenueInfo
from app.schemas.venue import (
    VenueActivityLogOut,
    VenueBookingCreate,
    VenueBookingOut,
    VenueCreate,
    VenueOut,
    VenueUpdate,
)
from shared.exceptions.http import conflict, not_found


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    return json.loads(value)


def _capacity(layouts: list[dict]) -> int:
    """A venue's overall capacity is derived from its highest per-layout
    capacity, never entered separately (AC3)."""
    if not layouts:
        return 0
    return max(layout["capacity"] for layout in layouts)


def _to_out(row: VenueInfo) -> VenueOut:
    layouts = _as_list(row.layouts)
    return VenueOut(
        venueId=row.venueId,
        code=row.code,
        name=row.name,
        location=row.location,
        address=row.address,
        floor=row.floor,
        description=row.description,
        capacity=_capacity(layouts),
        facilities=_as_list(row.facilities),
        accessibility=_as_list(row.accessibility),
        layouts=layouts,
        operatingHours=_as_list(row.operatingHours),
        turnaroundMinutes=row.turnaroundMinutes,
        isActive=row.isActive,
    )


def _booking_to_out(row: VenueBooking) -> VenueBookingOut:
    return VenueBookingOut(
        bookingId=row.bookingId,
        venueId=row.venueId,
        eventId=row.eventId,
        requestedBy=row.requestedBy,
        status=row.status,
        startsAt=row.startsAt,
        endsAt=row.endsAt,
        setupStartsAt=row.setupStartsAt,
        teardownEndsAt=row.teardownEndsAt,
        requirementsSnapshot=row.requirementsSnapshot,
        decisionReason=row.decisionReason,
        reviewedBy=row.reviewedBy,
        reviewedAt=row.reviewedAt,
        createdAt=row.createdAt,
    )


def _diff_keyed_items(old_items: list[dict], new_items: list[dict], key: str, tracked: list[str]) -> dict:
    """Per-key diff for a list of dicts (e.g. operating hours keyed by day,
    layouts keyed by name) so the activity log records exactly what changed
    ("Mon opens: 08:00 -> 09:00") instead of dumping the whole before/after
    array for a single-field edit."""
    old_by_key = {item[key]: item for item in old_items}
    new_by_key = {item[key]: item for item in new_items}
    diff = {}
    for k in sorted(set(old_by_key) | set(new_by_key)):
        old_item, new_item = old_by_key.get(k), new_by_key.get(k)
        if old_item == new_item:
            continue
        if old_item is None:
            diff[k] = {"added": {f: new_item[f] for f in tracked}}
        elif new_item is None:
            diff[k] = {"removed": {f: old_item[f] for f in tracked}}
        else:
            field_diff = {f: {"old": old_item[f], "new": new_item[f]} for f in tracked if old_item[f] != new_item[f]}
            if field_diff:
                diff[k] = field_diff
    return diff


def _diff_set(old_items: list[str], new_items: list[str]) -> dict:
    old_set, new_set = set(old_items), set(new_items)
    added, removed = sorted(new_set - old_set), sorted(old_set - new_set)
    diff = {}
    if added:
        diff["added"] = added
    if removed:
        diff["removed"] = removed
    return diff


class VenueService:
    """Business logic for the venue catalogue and its bookings. Reads and
    writes go through the injected DAOs; this class owns the transaction
    boundary (commit/refresh) since a single use case, such as creating a
    venue, can span both the VenueDAO and the VenueActivityLogDAO writing
    through the same session."""

    def __init__(
        self,
        db: Session,
        venue_dao: VenueDAO,
        log_dao: VenueActivityLogDAO,
        booking_dao: VenueBookingDAO,
    ):
        self.db = db
        self.venue_dao = venue_dao
        self.log_dao = log_dao
        self.booking_dao = booking_dao

    def _require_venue(self, venue_id: str) -> VenueInfo:
        row = self.venue_dao.get_by_id(venue_id)
        if not row:
            raise not_found("Venue not found")
        return row

    def _require_booking(self, booking_id: str) -> VenueBooking:
        row = self.booking_dao.get_by_id(booking_id)
        if not row:
            raise not_found("Venue booking not found")
        return row

    def list_venues(self, include_retired: bool = False) -> list[VenueOut]:
        """Retired venues are excluded from search by default (AC4) without
        deleting them. They still exist and get_venue() can still fetch one
        directly, so existing booking history keeps resolving. include_retired
        is an explicit opt-in for a "show retired venues" view, not the default,
        so AC4's default search behaviour is unchanged."""
        return [_to_out(row) for row in self.venue_dao.list(include_retired)]

    def get_venue(self, venue_id: str) -> VenueOut:
        return _to_out(self._require_venue(venue_id))

    def create_venue(self, data: VenueCreate, caller: dict) -> VenueOut:
        row = VenueInfo(
            venueId=str(uuid4()),
            code=data.code,
            name=data.name,
            location=data.location,
            address=data.address,
            floor=data.floor,
            description=data.description,
            facilities=[f for f in data.facilities],
            accessibility=[a for a in data.accessibility],
            layouts=[layout.model_dump() for layout in data.layouts],
            operatingHours=[hours.model_dump() for hours in data.operatingHours],
            turnaroundMinutes=data.turnaroundMinutes,
            isActive=True,
            createdAt=datetime.utcnow(),
        )
        self.venue_dao.add(row)
        self.db.flush()
        self.log_dao.log(row.venueId, "created", caller, data.model_dump())
        self.db.commit()
        self.db.refresh(row)
        return _to_out(row)

    def update_venue(self, venue_id: str, data: VenueUpdate, caller: dict) -> VenueOut:
        row = self._require_venue(venue_id)
        updates = data.model_dump(exclude_unset=True)
        changes = {}
        for field, value in updates.items():
            old_value = getattr(row, field)
            if field == "layouts":
                value = [layout if isinstance(layout, dict) else layout.model_dump() for layout in value]
                diff = _diff_keyed_items(_as_list(old_value), value, "name", ["capacity"])
                if diff:
                    changes["layouts"] = diff
            elif field == "operatingHours":
                value = [hours if isinstance(hours, dict) else hours.model_dump() for hours in value]
                diff = _diff_keyed_items(_as_list(old_value), value, "day", ["opens", "closes"])
                if diff:
                    changes["operatingHours"] = diff
            elif field in ("facilities", "accessibility"):
                diff = _diff_set(_as_list(old_value), value)
                if diff:
                    changes[field] = diff
            else:
                if value != old_value:
                    changes[field] = {"old": old_value, "new": value}
            setattr(row, field, value)
        if changes:
            self.log_dao.log(venue_id, "updated", caller, changes)
        self.db.commit()
        self.db.refresh(row)
        return _to_out(row)

    def retire_venue(self, venue_id: str, caller: dict, confirm: bool = False) -> VenueOut:
        row = self._require_venue(venue_id)

        # AC5: an approved ("confirmed") booking still ahead of us blocks a
        # plain retire. The caller must see what it affects and explicitly
        # confirm before it takes effect.
        now = datetime.utcnow()
        affected = self.booking_dao.find_confirmed_upcoming(venue_id, now)
        if affected and not confirm:
            # Plain, non-technical wording only: this reaches the UI's warning
            # panel verbatim, and the UI itself (not this message) is what
            # offers the "Retire anyway" action, so this should describe the
            # situation, not instruct the caller how to resend a request.
            listing = "; ".join(
                f"event {b.eventId}, starting {b.startsAt.strftime('%d %b %Y, %I:%M %p')}" for b in affected
            )
            plural = "booking" if len(affected) == 1 else "bookings"
            raise conflict(
                f"This venue has {len(affected)} confirmed upcoming {plural} that would be affected: "
                f"{listing}."
            )

        row.isActive = False
        self.log_dao.log(venue_id, "retired", caller, {"isActive": {"old": True, "new": False}})
        self.db.commit()
        self.db.refresh(row)
        return _to_out(row)

    def get_activity_log(self, venue_id: str) -> list[VenueActivityLogOut]:
        self._require_venue(venue_id)
        rows = self.log_dao.list_for_venue(venue_id)
        return [
            VenueActivityLogOut(
                logId=row.logId,
                venueId=row.venueId,
                action=row.action,
                changedBy=row.changedBy,
                changedByName=row.changedByName,
                changedByRole=row.changedByRole,
                changes=row.changes,
                createdAt=row.createdAt,
            )
            for row in rows
        ]

    def create_booking(self, data: VenueBookingCreate, requested_by: str) -> VenueBookingOut:
        row = VenueBooking(
            bookingId=str(uuid4()),
            venueId=data.venueId,
            eventId=data.eventId,
            requestedBy=requested_by,
            status="pending",
            startsAt=data.startsAt,
            endsAt=data.endsAt,
            setupStartsAt=data.setupStartsAt,
            teardownEndsAt=data.teardownEndsAt,
            requirementsSnapshot=data.requirementsSnapshot,
            createdAt=datetime.utcnow(),
        )
        self.booking_dao.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _booking_to_out(row)

    def approve_booking(self, booking_id: str, reviewer_id: str, reason: str | None) -> VenueBookingOut:
        row = self._require_booking(booking_id)
        if row.status != "pending":
            raise conflict(f"Booking is already {row.status}")
        row.status = "approved"
        row.decisionReason = reason
        row.reviewedBy = reviewer_id
        row.reviewedAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return _booking_to_out(row)

    def reject_booking(self, booking_id: str, reviewer_id: str, reason: str | None) -> VenueBookingOut:
        row = self._require_booking(booking_id)
        if row.status != "pending":
            raise conflict(f"Booking is already {row.status}")
        row.status = "rejected"
        row.decisionReason = reason
        row.reviewedBy = reviewer_id
        row.reviewedAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return _booking_to_out(row)
