"""What "the arrangements are confirmed" means, shared by readiness (SPM-5),
the safety review gate (SPM-120, SPM-121 AC2), and confirmation (SPM-72), so they can never
disagree. Pure functions over rows already fetched from venue-service and
equipment-service."""

from datetime import datetime, timezone

# Requests equipment-service raised for itself when a coordinator reserved
# straight from the catalogue quantity check. They are bookkeeping, not lines
# anyone asked for, so only their reservations count.
CATALOGUE_NOTE = "Reserved from the catalogue quantity check"
HOLDING_RESERVATIONS = ("active", "reserved")
# Venue bookings that are part of the event's arrangement.
LIVE_BOOKINGS = ("pending", "approved")
# Equipment requests that are settled: reserved or completed by technical
# support, or a shortfall the coordinator accepted.
SETTLED_REQUESTS = ("reserved", "complete", "resolved")
# What an unsettled request is waiting on, by its status.
WAITING_ON = {
    "pending": "is waiting for technical support to review it",
    "approved": "is approved but technical support have not reserved it yet",
    "partial": "is only partly reserved. Accept the shortfall or wait for technical support",
    "unavailable": "is unavailable. Accept the shortfall or wait for technical support",
}


def requested_lines(requests: list) -> list:
    """The equipment lines actually asked for: not rejected, cancelled, or catalogue bookkeeping."""
    return [
        row
        for row in requests
        if row.get("status") not in ("rejected", "cancelled") and row.get("reviewNote") != CATALOGUE_NOTE
    ]


def equipment_status(requests: list, reservations: list) -> str:
    """`ready`, `needs attention`, or `outstanding` for an event's equipment (SPM-5)."""
    real = [row for row in requests if row.get("status") != "rejected" and row.get("reviewNote") != CATALOGUE_NOTE]
    if real and all(row.get("status") == "complete" for row in real):
        return "ready"
    needed = sum(int(row.get("quantity") or 0) for row in real)
    active = sum(
        int(row.get("quantity") or 0) for row in reservations if row.get("status") in HOLDING_RESERVATIONS
    )
    attention = any(row.get("status") in ("partial", "unavailable", "attention") for row in real)
    attention = attention or any(row.get("status") in ("partial", "released") for row in reservations)
    if (needed and active >= needed and not attention) or (needed == 0 and active > 0 and not attention):
        return "ready"
    if attention:
        return "needs attention"
    return "outstanding"


def _when(value) -> datetime:
    """A naive UTC datetime, so times read with and without an offset compare."""
    when = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return when.astimezone(timezone.utc).replace(tzinfo=None) if when.tzinfo else when


def covers(booking: dict, starts_at: datetime | None, ends_at: datetime | None) -> bool:
    """The booking holds the venue for the whole of the event's current date and time."""
    if starts_at is None or ends_at is None:
        return False
    return _when(booking["startsAt"]) <= _when(starts_at) and _when(booking["endsAt"]) >= _when(ends_at)


def venue_gaps(bookings: list, starts_at: datetime | None, ends_at: datetime | None) -> list[dict]:
    """SPM-72 AC1, SPM-121 AC2: every requested venue is approved by venue staff,
    and every approved booking is for the event's date and time. A booking left
    at an earlier time after the event moved does not count."""
    live = [row for row in bookings if row.get("status") in LIVE_BOOKINGS]
    if not live:
        return [{"kind": "venue", "message": "No venue has been booked for this event yet."}]
    gaps = []
    for row in live:
        name = row.get("venueName") or row["venueId"]
        if row["status"] == "pending":
            gaps.append({"kind": "venue", "message": f"Venue staff have not approved the booking at {name} yet."})
        elif not covers(row, starts_at, ends_at):
            when = f"{_when(row['startsAt']):%d %b %Y %H:%M} to {_when(row['endsAt']):%d %b %Y %H:%M}"
            gaps.append(
                {
                    "kind": "venue",
                    "message": f"The booking at {name} ({when}) is not for the event's date and time. Cancel it "
                    "and request the venue for the event's time.",
                }
            )
    return gaps


def equipment_gaps(lines: list, requests: list, reservations: list, names: dict[str, str]) -> list[dict]:
    """SPM-72 AC1, SPM-121 AC2: every equipment request is reserved by technical
    support, and every equipment line on the event is either covered by held
    stock or recorded as not required (only those can be marked)."""
    gaps = []
    pending_types = set()
    for row in requested_lines(requests):
        if row.get("status") in SETTLED_REQUESTS:
            continue
        pending_types.add(row["equipmentId"])
        name = names.get(row["equipmentId"], row["equipmentId"])
        gaps.append(
            {
                "kind": "equipment",
                "message": f"{row['quantity']} × {name} "
                + WAITING_ON.get(row.get("status"), "needs technical support's attention")
                + ".",
            }
        )
    held: dict[str, int] = {}
    for row in reservations:
        if row.get("status") in HOLDING_RESERVATIONS:
            held[row["equipmentId"]] = held.get(row["equipmentId"], 0) + int(row.get("quantity") or 0)
    # Completed or accepted short: the request settled the line whatever is held.
    settled = {row["equipmentId"] for row in requested_lines(requests) if row.get("status") in ("complete", "resolved")}
    for line in lines:
        equipment_id = line["equipmentId"]
        if line.get("notRequired") or equipment_id in pending_types or equipment_id in settled:
            continue
        if held.get(equipment_id, 0) >= int(line.get("quantity") or 0):
            continue
        name = names.get(equipment_id, equipment_id)
        gaps.append(
            {
                "kind": "equipment",
                "equipmentId": equipment_id,
                "message": f"{line['quantity']} × {name} is neither reserved nor recorded as not required.",
            }
        )
    return gaps
