from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.venue_activity_log_dao import VenueActivityLogDAO
from app.dao.venue_booking_dao import VenueBookingDAO
from app.dao.venue_dao import VenueDAO
from app.dao.venue_unavailability_dao import VenueUnavailabilityDAO
from app.db.session import get_db
from app.orchestration.clients import fetch_event_facts, notify_venue_staff
from app.schemas.venue import (
    BookingReverificationRequest,
    SuitabilityOut,
    SuitabilityRequest,
    VenueActivityLogOut,
    VenueBookingCreate,
    VenueBookingDecision,
    VenueBookingOut,
    VenueCreate,
    VenueOut,
    VenueSearchResult,
    VenueUpdate,
)
from app.services.venue_service import VenueService
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.openapi import error_responses

router = APIRouter(
    prefix="/venues",
    tags=["venues"],
    responses=error_responses(401),
)

# SPM-17 AC1/AC5: only these roles can reach the catalogue at all; Event
# Organisers and Attendees are excluded, enforced here rather than only by
# hiding the tab in the frontend.
CATALOGUE_READER_ROLES = {"coordinator", "venue", "techsupport"}
# SPM-62: coordinators check before requesting a venue; Venue Staff can run
# the same check when assessing a request.
SUITABILITY_ROLES = {"coordinator", "venue"}
# SPM-63: coordinators follow their requests; Venue Staff work the pending queue.
BOOKING_READER_ROLES = {"coordinator", "venue"}
# SPM-61: coordinators shortlist venues for their events; Venue Staff can use the
# same search to find an alternative to suggest when they reject a request (SPM-10).
SEARCH_ROLES = {"coordinator", "venue"}


def get_venue_service(db: Session = Depends(get_db)) -> VenueService:
    return VenueService(
        db, VenueDAO(db), VenueActivityLogDAO(db), VenueBookingDAO(db), VenueUnavailabilityDAO(db)
    )


@router.get(
    "",
    response_model=list[VenueOut],
    summary="List venues",
    description=(
        "Venue catalogue for coordinators, venue staff, and technical support. "
        "Retired venues are omitted unless `includeRetired` is true."
    ),
    responses=error_responses(403, 503),
)
def list_venues(
    includeRetired: bool = Query(False, description="Include retired venues in the list."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return service.list_venues(include_retired=includeRetired)


@router.get(
    "/bookings",
    response_model=list[VenueBookingOut],
    summary="List venue booking requests",
    description=(
        "Coordinators and venue staff. Oldest first. `status=pending` is Venue Staff's pending queue; "
        "`eventId` shows an event's venue arrangement."
    ),
    responses=error_responses(403, 503),
)
def list_bookings(
    status: str | None = Query(None, description="`pending`, `approved`, `rejected`, or `withdrawn`."),
    eventId: str | None = Query(None, description="Only this event's requests."),
    venueId: str | None = Query(None, description="Only this venue's requests."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=BOOKING_READER_ROLES)
    return service.list_bookings(status, eventId, venueId)


@router.get(
    "/bookings/public-summary",
    summary="Approved venue name and location for an event",
    description="Any signed-in user. Does not include the venue catalogue or booking notes.",
)
def public_booking_summary(
    eventId: str = Query(..., description="Event id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url)
    return service.public_summary(eventId)


@router.get(
    "/bookings/{booking_id}",
    response_model=VenueBookingOut,
    summary="Get a venue booking request",
    description="Coordinators and venue staff. Includes the event facts, notes, and warnings sent with it.",
    responses=error_responses(403, 404, 503),
)
def get_booking(
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=BOOKING_READER_ROLES)
    return service.get_booking(booking_id)


@router.get(
    "/search",
    response_model=list[VenueSearchResult],
    summary="Search venues against an event's requirements",
    description=(
        "SPM-61. Active venues that fit every filter, ordered by name. With `startsAt` and `endsAt` (UTC), "
        "a venue is left out when the period falls outside its opening hours, or when a confirmed booking or "
        "an unavailability period overlaps the period widened by the venue's setup and turnaround time; "
        "another event's pending request only marks it `contested`. Pass `eventId` to ignore that event's own "
        "requests. `facility` and `accessibility` can be repeated. Coordinators and venue staff."
    ),
    responses=error_responses(403, 422, 503),
)
def search_venues(
    startsAt: datetime | None = Query(None, description="Start of the period, e.g. `2027-03-03T10:00:00Z`."),
    endsAt: datetime | None = Query(None, description="End of the period. Required when `startsAt` is given."),
    minCapacity: int = Query(0, ge=0, description="Expected attendance; capacity in the layout must reach it."),
    location: str | None = Query(None, description="Part of the venue's location, e.g. `HarbourFront`."),
    layout: str | None = Query(None, description="Required layout, e.g. `Theatre`."),
    facility: list[str] = Query(default=[], description="A required facility. Repeat for more than one."),
    accessibility: list[str] = Query(default=[], description="A required accessibility feature. Repeat for more."),
    eventId: str | None = Query(None, description="The event searching, so its own requests are not counted."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=SEARCH_ROLES)
    return service.search_venues(
        starts_at=startsAt,
        ends_at=endsAt,
        min_capacity=minCapacity,
        location=location,
        layout=layout,
        facilities=facility,
        accessibility=accessibility,
        exclude_event_id=eventId,
    )


@router.get(
    "/{venue_id}",
    response_model=VenueOut,
    summary="Get venue",
    description="Single venue, including retired ones. Coordinators, venue staff, and technical support only.",
    responses=error_responses(403, 404, 503),
)
def get_venue(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return service.get_venue(venue_id)


@router.post(
    "",
    response_model=VenueOut,
    status_code=201,
    summary="Create venue",
    description="Venue staff only. Capacity is derived from the highest layout capacity.",
    responses=error_responses(403, 503),
)
def create_venue(
    body: VenueCreate,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.create_venue(body, caller)


@router.patch(
    "/{venue_id}",
    response_model=VenueOut,
    summary="Update venue",
    description="Venue staff only. Partial update; omitted fields are left unchanged.",
    responses=error_responses(403, 404, 503),
)
def update_venue(
    body: VenueUpdate,
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.update_venue(venue_id, body, caller)


@router.post(
    "/{venue_id}/retire",
    response_model=VenueOut,
    summary="Retire venue",
    description=(
        "Venue staff only. Soft-deletes the venue (`isActive=false`). "
        "Fails with 409 if there are confirmed upcoming bookings unless `confirm` is true."
    ),
    responses=error_responses(403, 404, 409, 503),
)
def retire_venue(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    confirm: bool = Query(
        False, description="Required if confirmed upcoming bookings would be affected."
    ),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.retire_venue(venue_id, caller, confirm)


@router.get(
    "/{venue_id}/activity-log",
    response_model=list[VenueActivityLogOut],
    summary="Venue activity log",
    description="Create, update, and retire history for a venue. Coordinators, venue staff, and technical support only.",
    responses=error_responses(403, 404, 503),
)
def get_venue_activity_log(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return service.get_activity_log(venue_id)


@router.post(
    "/suitability",
    response_model=SuitabilityOut,
    summary="Check whether a venue suits an event",
    description=(
        "Coordinators and venue staff. Returns `suitable`, `suitable with warnings`, or `not suitable`, "
        "with a reason for every failure or warning. Anything not sent is taken from the event record. "
        "All times are UTC."
    ),
    responses=error_responses(403, 404, 503),
)
def check_suitability(
    body: SuitabilityRequest,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=SUITABILITY_ROLES)
    event = fetch_event_facts(body.eventId, authorization)
    return service.check_suitability(body, event)


@router.post(
    "/bookings",
    response_model=VenueBookingOut,
    status_code=201,
    summary="Request a venue booking",
    description=(
        "Only the event's assigned coordinator, for an event approved for planning. Refused with 409 when the "
        "venue fails the suitability check, when warnings are not acknowledged (`acknowledgeWarnings`), or when "
        "the event already has a pending request. Venue Staff are notified."
    ),
    responses=error_responses(403, 404, 409, 503),
)
def create_booking(
    body: VenueBookingCreate,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    event = fetch_event_facts(body.eventId, authorization)
    booking = service.request_booking(body, caller, event)
    notify_venue_staff(*service.venue_staff_notice(booking, "requested"), authorization)
    return booking


@router.post(
    "/bookings/reverification",
    response_model=list[VenueBookingOut],
    summary="Mark an event's confirmed bookings for re-verification",
    description="Coordinators only (SPM-71 AC4). Called by event-service when a significant event change "
    "is saved. Each `approved` booking for the event gets `needsReverification` and the reason; its "
    "status is unchanged, so the venue stays held. Returns the bookings marked.",
    responses=error_responses(403, 503),
)
def flag_bookings_for_reverification(
    body: BookingReverificationRequest,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.flag_for_reverification(body.eventId, body.reason)


@router.post(
    "/bookings/{booking_id}/withdraw",
    response_model=VenueBookingOut,
    summary="Withdraw a venue booking request",
    description="The event's assigned coordinator (SPM-46), while it is still pending. Venue Staff are notified.",
    responses=error_responses(403, 404, 409, 503),
)
def withdraw_booking(
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    event = fetch_event_facts(service.get_booking(booking_id).eventId, authorization)
    booking = service.withdraw_booking(booking_id, caller, event.coordinatorId)
    notify_venue_staff(*service.venue_staff_notice(booking, "withdrawn"), authorization)
    return booking


@router.post(
    "/bookings/{booking_id}/approve",
    response_model=VenueBookingOut,
    summary="Approve a venue booking",
    description="Venue staff only. Fails with 409 if the booking is no longer `pending`.",
    responses=error_responses(403, 404, 409, 503),
)
def approve_booking(
    body: VenueBookingDecision,
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.approve_booking(booking_id, caller["userId"], body.reason)


@router.post(
    "/bookings/{booking_id}/reject",
    response_model=VenueBookingOut,
    summary="Reject a venue booking",
    description="Venue staff only. Fails with 409 if the booking is no longer `pending`.",
    responses=error_responses(403, 404, 409, 503),
)
def reject_booking(
    body: VenueBookingDecision,
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.reject_booking(booking_id, caller["userId"], body.reason)
