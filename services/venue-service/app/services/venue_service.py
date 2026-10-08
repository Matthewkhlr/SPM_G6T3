import json
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.dao.venue_activity_log_dao import VenueActivityLogDAO
from app.dao.venue_booking_dao import VenueBookingDAO
from app.dao.venue_dao import VenueDAO
from app.dao.venue_unavailability_dao import VenueUnavailabilityDAO
from app.models.venue_booking import VenueBooking
from app.models.venue_info import VenueInfo
from app.schemas.venue import (
    BookingClashOut,
    ClashingBooking,
    EventFacts,
    SuitabilityOut,
    SuitabilityRequest,
    VenueActivityLogOut,
    VenueBookingCreate,
    VenueBookingOut,
    VenueCreate,
    VenueOut,
    VenueSearchResult,
    VenueUpdate,
)
from app.services import occupancy, suitability, venue_search
from shared.exceptions.http import conflict, forbidden
from shared.services.base import BaseService

# SPM-63 AC1: "Planning" is the stage after approval. Event approval (SPM-69)
# writes `planning`; events approved before that may still read `approved`. Both count.
PLANNING_STATUSES = ("approved", "planning")
# MySQL's error number for SIGNAL, which the SPM-64 trigger raises on an overlapping approval.
SIGNALLED_ERROR = 1644
APPROVED_ELSEWHERE = (
    "Another request for this venue at an overlapping time, including setup and turnaround, "
    "was approved first, so this request cannot be approved."
)


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
        setupMinutes=row.setupMinutes,
        turnaroundMinutes=row.turnaroundMinutes,
        emergencyAccess=row.emergencyAccess or "",
        restrictions=row.restrictions or "",
        isActive=row.isActive,
    )


def _occupied_window(row: VenueBooking) -> tuple[datetime, datetime]:
    """SPM-112 AC1: a booking's occupied window is always worked out from its
    venue's current setup and turnaround times, so it never reports a window
    stored before those times changed. The stored columns are only a fallback."""
    if row.venue is None:
        return row.setupStartsAt, row.teardownEndsAt
    return occupancy.occupied_window(row.startsAt, row.endsAt, row.venue.setupMinutes, row.venue.turnaroundMinutes)


def _booking_to_out(row: VenueBooking) -> VenueBookingOut:
    setup_from, turnaround_until = _occupied_window(row)
    return VenueBookingOut(
        bookingId=row.bookingId,
        venueId=row.venueId,
        eventId=row.eventId,
        requestedBy=row.requestedBy,
        status=row.status,
        startsAt=row.startsAt,
        endsAt=row.endsAt,
        setupStartsAt=setup_from,
        teardownEndsAt=turnaround_until,
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


def _clashing(row: VenueBooking, window: tuple[datetime, datetime]) -> ClashingBooking:
    """SPM-122 AC2 and AC3: a clashing booking reported as it stands, never changed."""
    return ClashingBooking(
        bookingId=row.bookingId,
        eventId=row.eventId,
        eventName=(row.eventSnapshot or {}).get("eventName"),
        status=row.status,
        startsAt=row.startsAt,
        endsAt=row.endsAt,
        setupStartsAt=window[0],
        teardownEndsAt=window[1],
    )


def _approval_blocked(venue: VenueInfo, held: occupancy.Commitments) -> str:
    """SPM-64 AC3, AC4 and AC7: why an approval was refused, naming the clash."""
    if held.confirmed:
        booking = held.confirmed[0]
        when = suitability._span(
            *occupancy.occupied_window(booking.startsAt, booking.endsAt, venue.setupMinutes, venue.turnaroundMinutes)
        )
        return (
            f"{venue.name} is already confirmed for {suitability._event_label(booking)} at an overlapping time "
            f"({when}, including setup and turnaround), so this request cannot be approved."
        )
    period = held.unavailability[0]
    why = f" ({period.reason})" if period.reason else ""
    return (
        f"{venue.name} is unavailable from {suitability._span(period.startsAt, period.endsAt)}{why}, "
        "so this request cannot be approved."
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


class VenueService(BaseService):
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
        super().__init__(db)
        self.venue_dao = venue_dao
        self.log_dao = log_dao
        self.booking_dao = booking_dao
        self.unavailability_dao = unavailability_dao

    def _require_venue(self, venue_id: str) -> VenueInfo:
        return self._require(self.venue_dao.get_by_id(venue_id), "Venue not found")

    def _require_booking(self, booking_id: str) -> VenueBooking:
        return self._require(self.booking_dao.get_by_id(booking_id), "Venue booking not found")

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
            setupMinutes=data.setupMinutes,
            turnaroundMinutes=data.turnaroundMinutes,
            emergencyAccess=data.emergencyAccess,
            restrictions=data.restrictions,
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

    def commitments(
        self,
        venue: VenueOut | VenueInfo,
        starts_at: datetime,
        ends_at: datetime,
        exclude_event_id: str | None = None,
        lock: bool = False,
    ) -> occupancy.Commitments:
        """SPM-64 AC1: the one rule for what already holds `venue` while an event
        from `starts_at` to `ends_at` would occupy it, setup and turnaround
        included. Search, suitability and booking approval all use it."""
        window = occupancy.occupied_window(starts_at, ends_at, venue.setupMinutes, venue.turnaroundMinutes)
        reach = occupancy.reach(venue.setupMinutes, venue.turnaroundMinutes)
        nearby = self.booking_dao.find_event_times_overlapping(
            venue.venueId, starts_at - reach, ends_at + reach, exclude_event_id, lock
        )
        return occupancy.Commitments(
            confirmed=[booking for booking in nearby if booking.status == "approved"],
            pending=[booking for booking in nearby if booking.status == "pending"],
            # AC4: an unavailability period conflicts when it overlaps the occupied window.
            unavailability=self.unavailability_dao.find_overlapping(venue.venueId, *window),
        )

    def booking_clashes(self, venue_id: str | None = None) -> list[BookingClashOut]:
        """SPM-122 AC1 and AC2: every pair of confirmed bookings on the same venue
        whose occupied windows overlap under the venue's current setup and turnaround
        times (Week 7 change 1), with both events and the overlapping times. Such
        pairs arise when a venue's times grow after its bookings were approved.
        AC3 and AC4: this only reads; no booking or event record is changed."""
        if venue_id:
            self._require_venue(venue_id)
        rows = self.booking_dao.list_confirmed_by_venue(venue_id)
        windows = [_occupied_window(row) for row in rows]
        clashes = []
        for i, (first, first_window) in enumerate(zip(rows, windows)):
            for second, second_window in zip(rows[i + 1 :], windows[i + 1 :]):
                # One venue's bookings share its setup and turnaround, so they come
                # in window order; once a window starts after this one ends, so do
                # the rest. Windows that only touch do not clash (SPM-112 AC3).
                if second.venueId != first.venueId or second_window[0] >= first_window[1]:
                    break
                clashes.append(
                    BookingClashOut(
                        venueId=first.venueId,
                        venueName=first.venue.name,
                        setupMinutes=first.venue.setupMinutes,
                        turnaroundMinutes=first.venue.turnaroundMinutes,
                        first=_clashing(first, first_window),
                        second=_clashing(second, second_window),
                        overlapStartsAt=second_window[0],
                        overlapEndsAt=min(first_window[1], second_window[1]),
                    )
                )
        return clashes

    def check_suitability(self, request: SuitabilityRequest, event: EventFacts) -> SuitabilityOut:
        """SPM-62. The one entry point every caller uses, so search, booking
        requests and re-verification all get the same verdict (AC9)."""
        venue = self.get_venue(request.venueId)
        needs = suitability.needs_for(request, event)
        bookings, unavailability = [], []
        period = suitability.event_period(needs)
        if period:
            held = self.commitments(venue, *period, exclude_event_id=request.eventId)
            bookings, unavailability = held.confirmed + held.pending, held.unavailability
        verdict, reasons = suitability.assess(venue, needs, bookings, unavailability)
        return SuitabilityOut(eventId=request.eventId, venueId=venue.venueId, verdict=verdict, reasons=reasons)

    def search_venues(
        self,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        min_capacity: int = 0,
        location: str | None = None,
        layout: str | None = None,
        facilities: list[str] | None = None,
        accessibility: list[str] | None = None,
        exclude_event_id: str | None = None,
    ) -> list[VenueSearchResult]:
        """SPM-61: the shortlist of active venues that fit the requirements and,
        when a period is given, are free for it. Without a period only the
        venue's own facts are checked."""
        if (starts_at is None) != (ends_at is None):
            raise HTTPException(
                status_code=422,
                detail="Give both a start and an end time to search a period, or leave both out.",
            )
        starts_at, ends_at = suitability._utc(starts_at), suitability._utc(ends_at)
        if starts_at is not None and ends_at <= starts_at:
            raise HTTPException(
                status_code=422,
                detail="The end time must be after the start time.",
            )
        filters = venue_search.SearchFilters(
            starts_at=starts_at,
            ends_at=ends_at,
            min_capacity=min_capacity,
            location=location,
            layout=layout,
            facilities=facilities or [],
            accessibility=accessibility or [],
        )
        results = []
        for venue in self.list_venues():
            capacity = venue_search.fits(venue, filters)
            if capacity is None:
                continue
            contested = False
            if filters.has_period:
                # AC3: a confirmed booking or unavailability excludes the venue (the SPM-64
                # rule); AC9: another event's pending request only marks it contested.
                held = self.commitments(venue, starts_at, ends_at, exclude_event_id=exclude_event_id)
                if held.conflicts:
                    continue
                contested = bool(held.pending)
            results.append(
                VenueSearchResult(
                    venueId=venue.venueId,
                    code=venue.code,
                    name=venue.name,
                    location=venue.location,
                    capacity=venue.capacity,
                    layout=layout.strip() if layout and layout.strip() else None,
                    layoutCapacity=capacity,
                    headroom=capacity - min_capacity,
                    setupMinutes=venue.setupMinutes,
                    turnaroundMinutes=venue.turnaroundMinutes,
                    contested=contested,
                )
            )
        return sorted(results, key=lambda row: row.name.casefold())

    def create_booking(
        self,
        data: VenueBookingCreate,
        requested_by: str,
        event_snapshot: dict | None = None,
        warnings: list[str] | None = None,
    ) -> VenueBookingOut:
        venue = self._require_venue(data.venueId)
        # SPM-64 AC2: the stored window is the venue's own setup and turnaround around the event.
        setup_from, turnaround_until = occupancy.occupied_window(
            data.startsAt, data.endsAt, venue.setupMinutes, venue.turnaroundMinutes
        )
        row = VenueBooking(
            bookingId=str(uuid4()),
            venueId=data.venueId,
            eventId=data.eventId,
            requestedBy=requested_by,
            status="pending",
            startsAt=data.startsAt,
            endsAt=data.endsAt,
            setupStartsAt=setup_from,
            teardownEndsAt=turnaround_until,
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

        # SPM-114: an event may hold several venues at once. The same venue is
        # not requested again while a pending or approved booking for it remains.
        live = self.booking_dao.find_live_for_event_venue(data.eventId, data.venueId)
        if live:
            article = "an" if live.status == "approved" else "a"
            raise conflict(
                f"This event already has {article} {live.status} booking for {self._venue_name(data.venueId)}. "
                "Withdraw, reject, or cancel that booking before requesting this venue again."
            )

        # AC3 and AC4: the SPM-62 rule decides; failures block, warnings need an acknowledgement.
        check = self.check_suitability(
            SuitabilityRequest(
                eventId=data.eventId,
                venueId=data.venueId,
                startsAt=data.startsAt,
                endsAt=data.endsAt,
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

    def public_summary(self, event_id: str) -> dict:
        """Approved booking's venue name and location, for attendees (SPM-91)."""
        bookings = self.booking_dao.list("approved", event_id, None)
        if not bookings:
            return {"eventId": event_id, "venueName": "", "location": ""}
        venue = self.venue_dao.get_by_id(bookings[0].venueId)
        return {
            "eventId": event_id,
            "venueName": venue.name if venue else "",
            "location": venue.location if venue else "",
        }

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

    def withdraw_booking(self, booking_id: str, caller: dict, event_coordinator_id: str | None) -> VenueBookingOut:
        """SPM-63 AC8. A withdrawn request no longer counts anywhere: the
        suitability rule and conflict checks only look at pending and approved.

        SPM-46 AC3: the event's current coordinator withdraws it, so after a
        reassignment the new coordinator can and the previous one cannot."""
        row = self._require_booking(booking_id)
        if not event_coordinator_id or event_coordinator_id != caller["userId"]:
            raise forbidden("Only the coordinator assigned to this event can withdraw its venue request.")
        if row.status != "pending":
            raise conflict(f"Only a pending request can be withdrawn. This request is already {row.status}.")
        row.status = "withdrawn"
        self.db.commit()
        self.db.refresh(row)
        return _booking_to_out(row)

    def cancel_booking(self, booking_id: str, caller: dict, event_coordinator_id: str | None) -> VenueBookingOut:
        """SPM-114: release one approved booking. The event's other bookings stay."""
        row = self._require_booking(booking_id)
        assigned = event_coordinator_id and event_coordinator_id == caller["userId"]
        if caller.get("role") != "venue" and not assigned:
            raise forbidden(
                "Only the coordinator assigned to this event, or Venue Staff, can cancel an approved booking."
            )
        if row.status != "approved":
            raise conflict(f"Only an approved booking can be cancelled. This booking is already {row.status}.")
        row.status = "cancelled"
        self.db.commit()
        self.db.refresh(row)
        return _booking_to_out(row)

    def check_release_allowed(self, caller: dict, event: EventFacts) -> None:
        """Only the people who can cancel the event (SPM-88 AC1) may release its
        bookings: its assigned coordinator, or an organiser from its own client
        organisation. Anyone else would be freeing another event's rooms."""
        if caller.get("role") == "coordinator" and event.coordinatorId and caller["userId"] == event.coordinatorId:
            return
        if caller.get("role") == "organiser" and event.organisationId and caller.get("organisationId") == event.organisationId:
            return
        raise forbidden("Only the coordinator assigned to this event, or its organiser, can release its venue bookings.")

    def release_event_bookings(self, event_id: str) -> list[VenueBookingOut]:
        """SPM-114: cancelling the event frees every pending request and approved booking.

        Rejected, withdrawn, and already cancelled rows are left as they are.
        """
        rows = self.booking_dao.list_open_for_event(event_id)
        for row in rows:
            row.status = "cancelled"
        self.db.commit()
        return [_booking_to_out(row) for row in rows]

    def arrangements_complete(self, event_id: str) -> bool:
        """True only when the event has requested venues and every one of them is approved.

        Pending requests are still requested. Withdrawn, rejected, and cancelled
        rows are no longer part of the arrangement.
        """
        requested = self.booking_dao.list_open_for_event(event_id)
        return bool(requested) and all(row.status == "approved" for row in requested)

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
        if action == "cancelled":
            return (
                f"Venue booking cancelled: {event} at {venue}",
                f"The booking of {venue} for {event}, {when}, has been cancelled. The venue is free for that time.",
            )
        return (
            f"Venue request withdrawn: {event} at {venue}",
            f"The coordinator has withdrawn their request for {venue} for {event}, {when}. No action is needed.",
        )

    def approve_booking(self, booking_id: str, reviewer_id: str, reason: str | None) -> VenueBookingOut:
        """Approval is where a venue becomes committed, so it applies the SPM-64
        rule: refused when a confirmed booking or unavailability overlaps the
        occupied window (AC3, AC4). The nearby bookings are read with a lock, which
        in MySQL also covers the gaps between them, so two approvals for clashing
        requests are checked one after the other and only one can pass (AC7).
        The database refuses an overlap on its own as well (AC3)."""
        row = self._require_booking(booking_id)
        if row.status != "pending":
            raise conflict(f"Booking is already {row.status}")
        venue = self._require_venue(row.venueId)
        # The request itself is pending, and pending requests never block, so it needs no exclusion.
        held = self.commitments(venue, row.startsAt, row.endsAt, lock=True)
        if held.conflicts:
            raise conflict(_approval_blocked(venue, held))
        row.setupStartsAt, row.teardownEndsAt = occupancy.occupied_window(
            row.startsAt, row.endsAt, venue.setupMinutes, venue.turnaroundMinutes
        )
        row.status = "approved"
        row.decisionReason = reason
        row.reviewedBy = reviewer_id
        row.reviewedAt = datetime.utcnow()
        try:
            self.db.commit()
        except DBAPIError as exc:
            self.db.rollback()
            if getattr(exc.orig, "args", (None,))[0] == SIGNALLED_ERROR:
                raise conflict(APPROVED_ELSEWHERE) from exc
            raise
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
