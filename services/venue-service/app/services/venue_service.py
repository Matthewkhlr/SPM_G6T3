import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.dao.venue_activity_log_dao import VenueActivityLogDAO
from app.dao.venue_booking_dao import VenueBookingDAO
from app.dao.venue_dao import VenueDAO
from app.dao.venue_unavailability_dao import VenueUnavailabilityDAO
from app.models.venue_booking import VenueBooking
from app.models.venue_info import VenueInfo
from app.schemas.venue import (
    EventFacts,
    SuitabilityOut,
    SuitabilityRequest,
    VenueActivityLogOut,
    VenueBookingCreate,
    VenueBookingOut,
    VenueCreate,
    VenueOut,
    VenueUpdate,
)
from app.services import suitability
from shared.exceptions.http import conflict, forbidden, not_found

# SPM-63 AC1: "Planning" is the stage after approval. Event approval (SPM-69)
# writes `approved`; seed data also uses `planning`. Both count.
PLANNING_STATUSES = ("approved", "planning")


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
        eventSnapshot=row.eventSnapshot,
        coordinatorNotes=row.coordinatorNotes or "",
        warnings=row.warnings or [],
        venueName=row.venue.name if row.venue else None,
        needsReverification=bool(row.needsReverification),
        reverificationNote=row.reverificationNote,
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _event_snapshot(event: EventFacts) -> dict:
    """SPM-63 AC2: what Venue Staff need to assess the request, copied from the
    event record so later edits to the event do not rewrite the request.
    event-service resolves the client organisation's name; if it could not,
    the organisation's id still says which client the request is for."""
    return {
        "eventName": event.eventName,
        "clientOrganisation": event.organisationName or event.organisationId or "",
        "startsAt": _iso(event.proposedStartAt),
        "endsAt": _iso(event.proposedEndAt),
        "expectedAttendance": event.expectedAttendance,
        "layout": event.layoutPreference or "",
        "accessibilityNeeds": event.accessibilityNeeds,
        "requiredFacilities": event.venueRequirements,
    }


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
        unavailability_dao: VenueUnavailabilityDAO,
    ):
        self.db = db
        self.venue_dao = venue_dao
        self.log_dao = log_dao
        self.booking_dao = booking_dao
        self.unavailability_dao = unavailability_dao

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
                f"event {b.eventId}, starting {b.startsAt.strftime('%d %b %Y, %I:%M %p')} UTC" for b in affected
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

    def check_suitability(self, request: SuitabilityRequest, event: EventFacts) -> SuitabilityOut:
        """SPM-62. The one entry point every caller uses, so search, booking
        requests and re-verification all get the same verdict (AC9)."""
        venue = self.get_venue(request.venueId)
        needs = suitability.needs_for(request, event)
        bookings, unavailability = [], []
        window = suitability.occupied_window(needs)
        if window:
            bookings = self.booking_dao.find_overlapping(venue.venueId, *window, exclude_event_id=request.eventId)
            unavailability = self.unavailability_dao.find_overlapping(venue.venueId, *window)
        verdict, reasons = suitability.assess(venue, needs, bookings, unavailability)
        return SuitabilityOut(eventId=request.eventId, venueId=venue.venueId, verdict=verdict, reasons=reasons)

    def create_booking(
        self,
        data: VenueBookingCreate,
        requested_by: str,
        event_snapshot: dict | None = None,
        warnings: list[str] | None = None,
    ) -> VenueBookingOut:
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
            eventSnapshot=event_snapshot,
            coordinatorNotes=data.coordinatorNotes,
            warnings=warnings or [],
            createdAt=datetime.utcnow(),
        )
        self.booking_dao.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _booking_to_out(row)

    def request_booking(self, data: VenueBookingCreate, caller: dict, event: EventFacts) -> VenueBookingOut:
        """SPM-63: a coordinator's venue booking request. Every rule below is
        checked before anything is saved, so a refused request leaves no trace."""
        # AC1: only the event's assigned coordinator, only once it is in planning.
        if event.coordinatorId != caller["userId"]:
            raise forbidden("Only the coordinator assigned to this event can request a venue for it.")
        if event.status not in PLANNING_STATUSES:
            raise conflict(
                "A venue can only be requested once the event has been approved for planning. "
                f"This event is currently {event.status or 'not yet approved'}."
            )

        # AC7: one pending request per event at a time.
        pending = self.booking_dao.find_pending_for_event(data.eventId)
        if pending:
            raise conflict(
                f"This event already has a pending venue request for {self._venue_name(pending.venueId)}. "
                "Withdraw it before requesting a different venue."
            )

        # AC3 and AC4: the SPM-62 rule decides; failures block, warnings need an acknowledgement.
        check = self.check_suitability(
            SuitabilityRequest(
                eventId=data.eventId,
                venueId=data.venueId,
                startsAt=data.startsAt,
                endsAt=data.endsAt,
                setupStartsAt=data.setupStartsAt,
                teardownEndsAt=data.teardownEndsAt,
            ),
            event,
        )
        failures = [reason.message for reason in check.reasons if reason.severity == "failure"]
        warnings = [reason.message for reason in check.reasons if reason.severity == "warning"]
        if failures:
            raise conflict("This venue is not suitable for this event, so the request cannot be sent. " + " ".join(failures))
        if warnings and not data.acknowledgeWarnings:
            raise conflict(
                "This venue has warnings. Please read them and confirm before sending the request. " + " ".join(warnings)
            )

        # AC2: the request carries the event's facts as they are now.
        return self.create_booking(data, caller["userId"], _event_snapshot(event), warnings)

    def list_bookings(
        self, status: str | None = None, event_id: str | None = None, venue_id: str | None = None
    ) -> list[VenueBookingOut]:
        return [_booking_to_out(row) for row in self.booking_dao.list(status, event_id, venue_id)]

    def get_booking(self, booking_id: str) -> VenueBookingOut:
        return _booking_to_out(self._require_booking(booking_id))

    def flag_for_reverification(self, event_id: str, reason: str) -> list[VenueBookingOut]:
        """SPM-71 AC4: mark the event's confirmed bookings as needing
        re-verification. They stay approved, so the venue stays held."""
        rows = self.booking_dao.list("approved", event_id, None)
        for row in rows:
            row.needsReverification = True
            row.reverificationNote = reason
        self.db.commit()
        return [_booking_to_out(row) for row in rows]

    def withdraw_booking(self, booking_id: str, caller: dict) -> VenueBookingOut:
        """SPM-63 AC8. A withdrawn request no longer counts anywhere: the
        suitability rule and conflict checks only look at pending and approved."""
        row = self._require_booking(booking_id)
        if row.requestedBy != caller["userId"]:
            raise forbidden("You can only withdraw venue requests that you sent.")
        if row.status != "pending":
            raise conflict(f"Only a pending request can be withdrawn. This request is already {row.status}.")
        row.status = "withdrawn"
        self.db.commit()
        self.db.refresh(row)
        return _booking_to_out(row)

    def _venue_name(self, venue_id: str) -> str:
        row = self.venue_dao.get_by_id(venue_id)
        return row.name if row else venue_id

    def venue_staff_notice(self, booking: VenueBookingOut, action: str) -> tuple[str, str]:
        """The subject and body sent to Venue Staff when a request is sent (AC5) or withdrawn (AC8)."""
        facts = booking.eventSnapshot or {}
        event = facts.get("eventName") or f"event {booking.eventId}"
        venue = self._venue_name(booking.venueId)
        when = f"{booking.startsAt:%d %b %Y, %I:%M %p} to {booking.endsAt:%d %b %Y, %I:%M %p} UTC"
        if action == "requested":
            return (
                f"New venue request: {event} at {venue}",
                f"A coordinator has requested {venue} for {event}, {when}. It is waiting in your pending queue.",
            )
        return (
            f"Venue request withdrawn: {event} at {venue}",
            f"The coordinator has withdrawn their request for {venue} for {event}, {when}. No action is needed.",
        )

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
