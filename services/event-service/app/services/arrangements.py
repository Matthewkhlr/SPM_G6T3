"""What "the equipment is arranged" means, shared by readiness (SPM-5) and the
safety review gate (SPM-120), so the two can never disagree."""

# Requests equipment-service raised for itself when a coordinator reserved
# straight from the catalogue quantity check. They are bookkeeping, not lines
# anyone asked for, so only their reservations count.
CATALOGUE_NOTE = "Reserved from the catalogue quantity check"
HOLDING_RESERVATIONS = ("active", "reserved")


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


def technical_confirmed(requests: list, reservations: list) -> bool:
    """SPM-120 AC1: every requested line is reserved or complete. An event that
    needs no equipment at all has nothing left to arrange."""
    open_reservations = [row for row in reservations if row.get("status") != "released"]
    if not requested_lines(requests) and not open_reservations:
        return True
    return equipment_status(requests, reservations) == "ready"
