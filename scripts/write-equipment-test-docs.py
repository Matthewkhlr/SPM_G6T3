#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "testing"
SHARED = (
    "Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. "
    "Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py."
)


def case(story, n, scenario, pre, steps, expected, data=SHARED):
    steps_txt = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    return f"""Item
Content
Test Case ID
TC-SPM{story}-AC{n:02d}
Test Scenario
{scenario}
Pre-conditions
{pre}
Test Steps
{steps_txt}
Test Data
{data}
Expected Result
{expected}
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.
"""


def write(code, title, count, spec, cases):
    header = f"""# {title}

Official story has {count} acceptance criteria.

Automated tests (TC-SPM{code}-AC01–AC{count:02d})
Command: npm run test:spm{code.lower()}
Spec: {spec}
Setup: docs/testing/README.md
Test data: {SHARED}

"""
    (ROOT / f"spm-{code.lower()}.md").write_text(header + "\n\n".join(cases), encoding="utf-8")


write("02", "SPM-2 Check equipment availability", 9, "e2e/spm02.spec.js", [
    case("02", 1, "Verify the check reports each requested line with the quantity requested and the quantity available for the event's date and time.",
         "TS-01 has created a type with 5 units. EC-01 has requested 2 of them on a planning event.",
         ["POST /equipment/availability for that event as TS-01.", "Read the line for the created type."],
         "The line shows requested 2 and available 5."),
    case("02", 2, "Verify the available quantity excludes units reserved for overlapping events.",
         "A type has 4 units. Another event already holds 2 for an overlapping period.",
         ["Reserve 2 units for the holder event.", "Check availability for a second overlapping event."],
         "Available quantity is 2."),
    case("02", 3, "Verify the available quantity excludes damaged, under maintenance, or retired units.",
         "A type has 6 units. One is damaged, one is under maintenance, one is retired.",
         ["PATCH the out-of-service counts.", "Check availability for an event that requests the type."],
         "Available quantity is 3."),
    case("02", 4, "Verify the check states whether the whole request can be met, and names each shortfall and by how much.",
         "A type has 2 units. The event requests 4.",
         ["POST /equipment/availability as TS-01.", "Read canMeet and the shortfall on the line."],
         "The check says the request cannot be met and names a shortfall of 2."),
    case("02", 5, "Verify a shortfall names the overlapping events that hold the conflicting quantities.",
         "A type has 3 units, all reserved to another overlapping event.",
         ["Reserve the holder event.", "Check availability for the second event."],
         "The shortfall lists the holder event so staff can negotiate."),
    case("02", 6, "Verify periods that merely touch do not compete for the same units.",
         "Event A ends at the same instant event B begins. A holds every unit.",
         ["Reserve all units for A.", "Check availability for B."],
         "B still sees the full stock."),
    case("02", 7, "Verify re-running the check after a reservation is made or released reflects the new position.",
         "A type has 5 free units.",
         ["Check availability.", "Reserve 2 on another overlapping event and check again.", "Release that reservation and check again."],
         "The figures move from 5 to 3 to 5."),
    case("02", 8, "Verify the check never itself reserves anything, and running it twice changes nothing.",
         "An event has a request and no reservation yet.",
         ["POST /equipment/availability twice.", "GET the type's reservations."],
         "Both checks match, and no reservation was created."),
    case("02", 9, "Verify automated coverage of exact sufficiency, a shortfall of one, an overlapping reservation, out-of-service stock, and touching periods.",
         "TS-01 can create isolated stock and events for each scenario.",
         ["Check a request whose quantity equals available stock.", "Check a request for available plus one.", "Reserve one overlapping unit and re-check.", "Mark one unit damaged and re-check.", "Reserve a touching period and re-check."],
         "Exact fit can be met, shortfall is 1, overlap and out-of-service reduce stock, and touching periods do not."),
])

write("03", "SPM-3 Reserve equipment for an event", 10, "e2e/spm03.spec.js", [
    case("03", 1, "Verify Technical Support Staff can reserve a quantity up to what is available for the event's period.",
         "A type has 4 free units. The event requests 3.",
         ["POST /equipment/reservations for quantity 3 as TS-01."],
         "The reservation is created for 3 units on that event."),
    case("03", 2, "Verify a quantity above what is available is refused, the available quantity is stated, and nothing is reserved.",
         "A type has 2 free units. The attempt is for 5.",
         ["POST /equipment/reservations for quantity 5.", "GET the type's reservations."],
         "The call is refused, available 2 is stated, and no row is stored."),
    case("03", 3, "Verify a reservation reduces the quantity available to any other overlapping event.",
         "A type has 5 units.",
         ["Reserve 2 for event A.", "Check availability for overlapping event B."],
         "B sees 3 available."),
    case("03", 4, "Verify units recorded as damaged, under maintenance, or retired can never be reserved.",
         "A type has 3 units, all out of service.",
         ["PATCH out-of-service counts to 3.", "POST a reservation for 1."],
         "The reservation is refused."),
    case("03", 5, "Verify when two reservations for the last available unit are submitted together, exactly one succeeds.",
         "A type has 1 unit. Two events request it for the same period.",
         ["POST both reservations at the same time.", "Read both responses."],
         "One is 201 and the other is refused with the shortfall explained."),
    case("03", 6, "Verify a reservation stays associated with its event and is visible on the event and the equipment record.",
         "TS-01 has reserved a created type for a planning event.",
         ["Open the event.", "Open the equipment record."],
         "Both screens show the same quantity, event, and period."),
    case("03", 7, "Verify the assigned coordinator can see the reservations and is notified when the request is fully reserved.",
         "EC-01 is assigned. TS-01 reserves the full requested quantity.",
         ["Sign in as EC-01 and open the event."],
         "The coordinator sees the reservation as fully reserved."),
    case("03", 8, "Verify cancelling, rejecting, or completing the event releases its reservations.",
         "A reservation exists on a newly assigned event.",
         ["Reject the event as EC-01.", "GET the reservation."],
         "The reservation is released and the units are free again."),
    case("03", 9, "Verify reservations and releases persist in the activity log with who acted and when.",
         "TS-01 reserved and then released a type.",
         ["GET /equipment/{id}/activity-log as TS-01."],
         "The log has a reserve row and a release row for u4."),
    case("03", 10, "Verify reserving the full requested quantity for every line marks the equipment arrangement ready.",
         "The event has one equipment line for 2 units.",
         ["Reserve 2.", "GET the event readiness as EC-01."],
         "The equipment arrangement is ready."),
])

write("04", "SPM-4 View upcoming events", 7, "e2e/spm04.spec.js", [
    case("04", 1, "Verify the queue lists upcoming events that have equipment requirements, soonest first.",
         "e1 and e2 have equipment lines. e1 is sooner.",
         ["GET /equipment/queue as TS-01."],
         "e1 and e2 are listed, e1 before e2."),
    case("04", 2, "Verify each row shows name, date, start and end time, status, venue if booked, coordinator, and equipment summary.",
         "e1 is AI in Events Summit, assigned to Ben Lee.",
         ["Sign in as TS-01 and open Upcoming Events.", "Read the e1 row."],
         "The row carries every required field."),
    case("04", 3, "Verify each row shows whether the request is awaiting review, partly reserved, fully reserved, or unavailable.",
         "e1 has a pending line and a reserved line. e3 has a partial LED-wall line.",
         ["Open Upcoming Events as TS-01.", "Read data-equipment-state on e1 and e3."],
         "The four request states are represented in plain language."),
    case("04", 4, "Verify requests needing attention, including re-verification, are shown first within the same date.",
         "e2 is flagged for re-verification.",
         ["GET /equipment/queue.", "Group rows by date and check order."],
         "Attention rows come first on their date. e2 is marked for re-verification."),
    case("04", 5, "Verify the queue can be filtered by status and date range, and completed and cancelled events are excluded by default.",
         "e8 is cancelled.",
         ["GET /equipment/queue.", "Open Upcoming Events and confirm e8 is absent.", "Set a status and date-range filter."],
         "Cancelled e8 is not in the default queue."),
    case("04", 6, "Verify events with no equipment requirements do not appear.",
         "e6 has empty equipment requirements.",
         ["GET /equipment/queue as TS-01."],
         "e6 is absent."),
    case("04", 7, "Verify Technical Support Staff can open an event from the queue to check availability and reserve.",
         "e1 is on the queue.",
         ["Open Upcoming Events as TS-01.", "Open the e1 row.", "Confirm the check and reserve controls."],
         "The event opens onto availability and reserve."),
])

write("75", "SPM-75 Equipment catalogue with quantities and operational status", 7, "e2e/spm75.spec.js", [
    case("75", 1, "Verify an equipment record holds a code, name, category, description, total quantity owned, home location, and optional technical notes.",
         "TS-01 can create catalogue records.",
         ["POST a new type.", "GET it back."],
         "Every published field is stored."),
    case("75", 2, "Verify each record carries unavailable counts for damaged, under maintenance, or retired, subtracted from the total rather than deleted.",
         "A type owns 6 units.",
         ["PATCH out-of-service to damaged 1, maintenance 2, retired 1."],
         "Total stays 6 and serviceable quantity is 2."),
    case("75", 3, "Verify the quantity available to reserve is total owned, minus out of service, minus overlapping reservations.",
         "A type owns 8 units, 2 out of service, 2 reserved for an overlapping event.",
         ["POST /equipment/availability for that period."],
         "Available quantity is 4."),
    case("75", 4, "Verify Technical Support Staff can add and edit records; other roles have read-only access, enforced on the server.",
         "eq1 exists.",
         ["GET eq1 as EC-01. Confirm 200.", "POST and PATCH as EC-01, VS-01, and ATT-01. Confirm 403.", "POST a type as TS-01. Confirm 201."],
         "Writes are technical-support only."),
    case("75", 5, "Verify an out-of-service count raised above the total owned is rejected.",
         "A type owns 3 units.",
         ["PATCH damaged 2 and maintenance 2."],
         "The change is rejected."),
    case("75", 6, "Verify raising out-of-service below already reserved stock lists the events, requires acknowledgement, and notifies coordinators.",
         "3 of 4 units are reserved for a future event.",
         ["PATCH damaged 2 without acknowledgement. Confirm 409 and the event is named.", "PATCH again with acknowledgement."],
         "The first save is blocked; the second succeeds."),
    case("75", 7, "Verify every change to quantities or out-of-service counts is written to the activity log.",
         "TS-01 has just changed total quantity and a damaged count.",
         ["GET /equipment/{id}/activity-log."],
         "The log records the quantity and out-of-service edits."),
])

write("76", "SPM-76 Record an event's equipment requirements", 4, "e2e/spm76.spec.js", [
    case("76", 1, "Verify a coordinator request captures equipment type, quantity, and technical requirements — not unit identifiers.",
         "e3 is in planning and assigned to EC-01.",
         ["POST /equipment/requests as EC-01 for eq1 quantity 2 with an HDMI note."],
         "The stored request has type, quantity, and the note, and no unit id."),
    case("76", 2, "Verify the request is visible to Technical Support as Requested, and only they can move it to Reserved or Unavailable.",
         "EC-01 has just created a request on e3.",
         ["GET the request as TS-01.", "POST reserve and unavailable as EC-01.", "PATCH status reserved as EC-01."],
         "Staff see Requested. Coordinator transitions are 403."),
    case("76", 3, "Verify once Technical Support acts, the record shows who last updated it and when.",
         "A pending request exists on e3.",
         ["POST /review as TS-01.", "Read reviewedBy and the timestamp."],
         "The updater is u4 and a time is stored for the readiness view to read."),
    case("76", 4, "Verify a line that cannot be fulfilled is marked accordingly and the coordinator is notified.",
         "EC-01 requested more eq3 than exists.",
         ["POST /unavailable as TS-01.", "Open e3 as EC-01."],
         "The request is unavailable and the coordinator can see the outcome."),
])

write("77", "SPM-77 Respond to an equipment request that cannot be fully met", 7, "e2e/spm77.spec.js", [
    case("77", 1, "Verify Technical Support can mark a line unavailable with a reason, optional note, and suggested alternative.",
         "A pending eq1 request exists on e3.",
         ["POST /unavailable with reason, note, and alternative eq2."],
         "The line is unavailable and names eq2 as the alternative."),
    case("77", 2, "Verify Technical Support can record a line as partly fulfilled, reserving what is available and stating the shortfall.",
         "A type has 2 units. The event asked for 4.",
         ["POST /partial with reservedQuantity 2."],
         "2 are reserved and the shortfall is 2."),
    case("77", 3, "Verify the assigned coordinator is notified with the line, the shortfall, the reason, and any suggested alternative.",
         "TS-01 marked an e3 eq3 line unavailable, suggesting eq1.",
         ["Open e3 as EC-01."],
         "The coordinator sees the line, the reason, and the alternative."),
    case("77", 4, "Verify a line marked unavailable or partly fulfilled shows the equipment arrangement as needing attention, not ready.",
         "e3 already has eq-shortfall partly fulfilled.",
         ["GET /events/e3/readiness as EC-01."],
         "The equipment arrangement needs attention."),
    case("77", 5, "Verify the coordinator can accept the shortfall, which resolves the line, or amend the request and send it back.",
         "Two shortfall lines exist on e3.",
         ["POST /accept-shortfall as EC-01 on the first.", "PATCH quantity and resubmit on the second."],
         "Accepting resolves the line. Amending returns it to Requested."),
    case("77", 6, "Verify recording the whole request as reviewed and complete marks the equipment arrangement ready.",
         "A new event has one equipment line.",
         ["POST /complete-review as TS-01.", "GET readiness."],
         "The equipment arrangement is ready."),
    case("77", 7, "Verify every response is written to the activity log with who acted and when.",
         "TS-01 has just marked a line unavailable.",
         ["GET the equipment activity log."],
         "The log records the response for u4."),
])

write("78", "SPM-78 Adjust or release an equipment reservation", 6, "e2e/spm78.spec.js", [
    case("78", 1, "Verify Technical Support can reduce, increase, or release a reservation on an event that is not Completed, Cancelled, or Rejected.",
         "A reservation of 2 exists on a planning event. A second reservation sits on an event that is then rejected.",
         ["PATCH quantity to 3, then 1.", "POST /release.", "PATCH the rejected event's reservation."],
         "Active events can be adjusted. Terminal events cannot."),
    case("78", 2, "Verify increasing a reservation is subject to the same availability check as making one.",
         "A type has 2 units and 1 is already reserved.",
         ["PATCH the reservation to quantity 5."],
         "The increase is refused and available stock is stated."),
    case("78", 3, "Verify reducing or releasing a reservation immediately returns the units to availability for the period.",
         "3 of 4 units are reserved. Another event is watching the same period.",
         ["Reduce to 1 and re-check.", "Release and re-check."],
         "Availability moves from 1 to 3 to 4."),
    case("78", 4, "Verify releasing a reservation on a confirmed event requires a reason and notifies the assigned coordinator and the Event Organiser.",
         "e1 is confirmed. TS-01 has reserved a created type on e1.",
         ["POST /release with no reason. Confirm 400 or 422.", "POST /release with a reason.", "Open e1 as EC-01 and as EO-01."],
         "A reason is mandatory. Both the coordinator and the organiser can see the release."),
    case("78", 5, "Verify releasing a reservation shows the event's equipment arrangement as needing attention again.",
         "A new event was fully reserved.",
         ["POST /release.", "GET readiness."],
         "The equipment arrangement needs attention."),
    case("78", 6, "Verify every adjustment and release is written to the activity log with previous quantity, new quantity, actor, and time.",
         "TS-01 reduced a reservation from 2 to 1.",
         ["GET the equipment activity log."],
         "The log has previous 2, new 1, and u4."),
])

print("wrote equipment test docs")
