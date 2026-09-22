#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "testing"
SHARED = (
    "Accounts EO-01, EO-04, EC-01, EC-02 from Test Data/credentials-valid.txt. "
    "Events e1, e3, e6, e8 and review rv-clarify-e3 from scripts/seed.py."
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


write("05", "SPM-5 Follow-up pending items of the given request", 9, "e2e/spm05.spec.js", [
    case("05", 1, "Verify the readiness table shows category, personnel, status, assignment date, and attachments.",
         "e1 is assigned to EC-01.",
         ["GET /events/e1/readiness as EC-01.", "Open the e1 readiness screen.", "Confirm each row has those columns."],
         "Every line item shows the five required fields."),
    case("05", 2, "Verify the coordinator can update a line item's readiness status.",
         "EC-01 can write readiness items on e1.",
         ["POST a venue line item.", "PATCH its status to in_progress.", "Confirm the stored status changed."],
         "The status update is persisted."),
    case("05", 3, "Verify contact information of assigned personnel is available for follow-up.",
         "e1 readiness items have handlers.",
         ["Open e1 readiness as EC-01.", "Confirm a handler contact (email or phone) is shown."],
         "The coordinator can reach the assigned person from the table."),
    case("05", 4, "Verify attachments of supporting documents can be viewed.",
         "A readiness row on e1 has an attachment.",
         ["Open e1 readiness.", "Confirm an attachment link is present and has an href."],
         "Supporting documents are reachable from the row."),
    case("05", 5, "Verify a line item can be created, modified, and deleted.",
         "EC-01 is assigned to e1.",
         ["POST a line item.", "PATCH its note.", "DELETE it.", "Confirm it is absent from the list."],
         "Create, update, and delete all persist."),
    case("05", 6, "Verify saved line-item information is recorded.",
         "A new registration line item is created on e1.",
         ["GET the item by id.", "Confirm category and note match what was saved."],
         "A later read returns the same values."),
    case("05", 7, "Verify confirming a status requires an explicit confirmation.",
         "EC-01 is on the e1 readiness screen.",
         ["Click confirm on the first row.", "Confirm the dialog appears.", "Confirm the status and see it settle."],
         "Status confirmation is not a silent toggle."),
    case("05", 8, "Verify a line item whose due date is near raises an alert.",
         "EC-01 creates an item due in two days.",
         ["POST the item.", "Confirm it is marked dueSoon.", "GET readiness?dueSoon=true and confirm it is listed."],
         "Near-due items are alerted."),
    case("05", 9, "Verify an overdue line item is flagged.",
         "EC-01 creates an item whose due date is in the past.",
         ["POST the item.", "Confirm overdue is true on the create response and on the list."],
         "Overdue items stay flagged until resolved."),
])

write("15", "SPM-15 View Event and preparation status", 9, "e2e/spm15.spec.js", [
    case("15", 1, "Verify the organiser sees their organisation's events, each with current status and proposed or confirmed date.",
         "EO-01 belongs to org-1. e1 and e6 are org-1 events. e5 is Beacon.",
         ["Sign in as EO-01 and open My Events.", "Confirm e1 shows a status and a date.", "Confirm e5 is absent."],
         "Only the organiser's organisation events appear, with status and date."),
    case("15", 2, "Verify drafts are distinguishable from submitted events in the list.",
         "EO-01 can create a draft. e6 is already submitted.",
         ["Create a draft request as EO-01.", "Open My Events.", "Confirm the draft row and e6 have different lifecycle markers."],
         "Drafts and submitted events are not drawn the same way."),
    case("15", 3, "Verify opening an event shows settled and outstanding arrangements in plain language.",
         "e1 has some confirmed arrangements.",
         ["Open e1 as EO-01.", "Confirm settled and outstanding copy.", "Confirm internal codes submitted/planning are not used as labels."],
         "Arrangements are described in plain language."),
    case("15", 4, "Verify anything awaiting the organiser is flagged and links straight to it.",
         "e3 has open clarification rv-clarify-e3.",
         ["Open e3 as EO-01.", "Confirm a needs-action flag.", "Open it and confirm the URL is the clarification or change-request screen."],
         "Action items are flagged and are links, not dead text."),
    case("15", 5, "Verify the organiser sees the assigned coordinator's name and contact details.",
         "e1 is assigned to Ben Lee (EC-01).",
         ["Open e1 as EO-01.", "Confirm Ben Lee and a contact address are shown."],
         "Coordinator identity and contact are visible once assigned."),
    case("15", 6, "Verify a confirmed event shows venue, date, time, layout, and equipment.",
         "e1 is confirmed at Marina Hall A.",
         ["Open e1 as EO-01.", "Confirm Marina Hall A, date, time, layout, and equipment."],
         "Confirmed facts are on the organiser event."),
    case("15", 7, "Verify the shown status matches the stored event status, with no stale value.",
         "GET /events/e1 returns the stored status.",
         ["GET /events/e1 as EO-01.", "Open e1.", "Confirm the on-screen status matches the stored status."],
         "The UI does not show a cached status that differs from the API."),
    case("15", 8, "Verify the organiser sees no internal notes, other clients, or unrelated venue or equipment records.",
         "e5 is Beacon. e1 is Apex.",
         ["Open e1 as EO-01.", "Confirm Beacon Q4 Showcase, internal notes, and unrelated venues are absent."],
         "The organiser view is limited to their event."),
    case("15", 9, "Verify an organiser with no events is pointed at creating a request.",
         "EO-04 belongs to org-3 and has no events.",
         ["Sign in as EO-04 and open My Events.", "Confirm an empty state that points at creating a first request."],
         "The empty list is a prompt to start a request, not a blank page."),
])

write("65", "SPM-65 Review queue of submitted requests", 7, "e2e/spm65.spec.js", [
    case("65", 1, "Verify the queue lists Submitted, Under Review, and Changes Requested, and excludes drafts.",
         "e6 is submitted. e3 is planning. EO-01 can create a draft.",
         ["Create a draft as EO-01.", "GET /events/queue as EC-01.", "Confirm e6 is present and both the draft and e3 are absent."],
         "Drafts never appear in the review queue."),
    case("65", 2, "Verify each row shows name, organisation, proposed datetime, attendance, status, coordinator, and submitted time.",
         "e6 is Unassigned Client Brief for Apex Partners.",
         ["Open Review Queue as EC-01.", "Confirm those fields on the e6 row."],
         "The row is complete enough to decide what to open."),
    case("65", 3, "Verify unassigned requests are distinguished and can be filtered on their own.",
         "e6 is unassigned. e1 is assigned.",
         ["Open Review Queue.", "Confirm e6 is marked unassigned.", "Filter to unassigned and confirm e1 is hidden."],
         "Unassigned work can be isolated."),
    case("65", 4, "Verify the queue can be sorted by submission time and proposed date, and defaults to the longest wait first.",
         "The queue has more than one request.",
         ["GET /events/queue.", "Confirm submittedAt is non-decreasing.", "GET /events/queue?sort=proposedStartAt and confirm it returns a list."],
         "Default order is oldest submission first."),
    case("65", 5, "Verify a coordinator can filter to only the events assigned to them.",
         "e6 is unassigned. e1–e4 are assigned to EC-01.",
         ["Filter to mine as EC-01.", "Confirm e6 is hidden.", "GET /events/queue?assignedTo=u2 and confirm every row is u2."],
         "The mine filter is assignment-scoped."),
    case("65", 6, "Verify a request whose proposed date is near is flagged using one shared threshold.",
         "EVENT_PROPOSED_DATE_NEAR_DAYS is the single threshold.",
         ["GET /events/queue.", "For every row flagged dateNear, confirm its proposed start is within that threshold."],
         "The near-date flag is not hard-coded per screen."),
    case("65", 7, "Verify an empty filter explains what is being excluded.",
         "EC-02 has no assigned queue items.",
         ["Sign in as EC-02, open Review Queue, filter to mine.", "Confirm the empty state mentions the filter."],
         "An empty filter is explained, not a blank table."),
])

write("66", "SPM-66 Assign a coordinator to a submitted event", 8, "e2e/spm66.spec.js", [
    case("66", 1, "Verify a coordinator can assign an unassigned submitted event to themselves or to another coordinator.",
         "EO-01 can create submitted events.",
         ["Create a submitted event and assign it to u2 as EC-01.", "Create another and assign it to EC-02 from the event screen."],
         "Self-assignment and assignment to a colleague both succeed."),
    case("66", 2, "Verify the candidate list shows each coordinator's current count of active events, as information only.",
         "EC-01 and EC-02 exist.",
         ["GET /events/coordinators as EC-01.", "Confirm u2 has a numeric activeEventCount."],
         "Workload is visible and is not a lock."),
    case("66", 3, "Verify assignment succeeds even when the chosen coordinator already holds many events.",
         "u2 already has e1–e4.",
         ["Assign a new submitted event to u2.", "Confirm HTTP 201."],
         "There is no workload cap."),
    case("66", 4, "Verify assignment records who assigned, who was assigned, and when.",
         "EC-01 assigns a new event to u6.",
         ["Read the assignment response.", "Read the event activity log.", "Confirm assignedBy u2, coordinatorId u6, and assignedAt."],
         "The activity log keeps the assignment."),
    case("66", 5, "Verify assignment notifies the new coordinator and the organiser, and the organiser can see name and contact.",
         "A new event is assigned to Ben Lee.",
         ["Open the event as EO-01.", "Confirm Ben Lee and a contact address."],
         "The organiser can see who to deal with."),
    case("66", 6, "Verify assigning moves the event from Submitted to Under Review.",
         "A freshly submitted event has no coordinator.",
         ["Assign u2.", "GET the event and confirm status Under Review."],
         "Assignment is the Submitted → Under Review transition."),
    case("66", 7, "Verify only Event Coordinators can assign; other roles get 403.",
         "A submitted event exists.",
         ["POST assign-coordinator as EO-01, VS-01, TS-01, and ATT-01.", "Confirm 403 each time."],
         "Wrong-role assignment is forbidden."),
    case("66", 8, "Verify an event cannot be assigned to a user who is not an Event Coordinator.",
         "u3 is Venue Staff.",
         ["POST assign-coordinator with coordinatorId u3 as EC-01.", "Confirm 400, 403, or 422."],
         "Only coordinators can be the assignee."),
])

write("68", "SPM-68 Request clarification or amendment from the organiser", 8, "e2e/spm68.spec.js", [
    case("68", 1, "Verify the coordinator can raise a clarification stating what is unclear and optionally naming the field.",
         "An Under Review event is assigned to EC-01.",
         ["POST a clarification on expectedAttendance.", "Confirm it is open and stores the message and field."],
         "The clarification is recorded on the event."),
    case("68", 2, "Verify raising a clarification moves the event to Changes Requested and notifies the organiser.",
         "An Under Review event exists.",
         ["POST a clarification.", "GET the event and confirm status Changes Requested."],
         "The event leaves Under Review until the gap is resolved."),
    case("68", 3, "Verify the clarification and the organiser's reply appear as an ordered thread with author, role, and time.",
         "e3 has rv-clarify-e3.",
         ["Open e3 as EO-01.", "Confirm the thread shows the clarification, a coordinator author, and a time."],
         "The conversation stays on the event."),
    case("68", 4, "Verify more than one clarification can be open independently.",
         "An Under Review event exists.",
         ["POST two clarifications.", "Confirm both remain open."],
         "Each clarification has its own status."),
    case("68", 5, "Verify marking every clarification resolved returns the event to Under Review.",
         "An event has one open clarification.",
         ["POST resolve on that clarification.", "GET the event and confirm Under Review."],
         "The event returns to review only when nothing is still open."),
    case("68", 6, "Verify threads are visible to the organiser and internal staff, and never to attendees.",
         "e3 has a clarification.",
         ["GET clarifications as EC-01 and EO-01. Confirm 200.", "GET as ATT-01. Confirm 403 or 404."],
         "Attendees cannot read clarification threads."),
    case("68", 7, "Verify threads remain readable after the event is confirmed, completed, or cancelled.",
         "e3 already has a stored clarification.",
         ["GET /events/e3/clarifications as EC-01.", "Confirm at least one entry is returned."],
         "History is not deleted when the event moves on."),
    case("68", 8, "Verify no clarification can be raised against a Draft event.",
         "EO-01 creates an event that is still draft/created.",
         ["POST a clarification as EC-01.", "Confirm 400, 409, or 422."],
         "Drafts are out of the review conversation."),
])

write("69", "SPM-69 Approve a submitted request so planning can begin", 6, "e2e/spm69.spec.js", [
    case("69", 1, "Verify the assigned coordinator can approve an Under Review event with an optional note.",
         "A newly assigned event is Under Review.",
         ["POST /approve with a note.", "Confirm status Planning and the note is stored."],
         "Approval is available to the assigned coordinator."),
    case("69", 2, "Verify approving moves the event to Planning and records the decider and time.",
         "An Under Review event is assigned to u2.",
         ["POST /approve.", "Confirm status Planning, decidedBy u2, and a timestamp."],
         "The decision is auditable."),
    case("69", 3, "Verify the organiser is notified and can see the outcome and any note.",
         "EC-01 approved an event with note Taken on.",
         ["Open the event as EO-01.", "Confirm the decision and note are visible."],
         "The organiser does not have to ask what happened."),
    case("69", 4, "Verify approving with open clarifications warns and requires confirmation.",
         "An Under Review event has an open clarification.",
         ["Open the event as EC-01 and click Approve.", "Confirm the warning.", "Confirm anyway and see Planning."],
         "Open clarifications do not silently block approval."),
    case("69", 5, "Verify approval is unavailable for an unassigned submitted event.",
         "e6 is submitted and unassigned.",
         ["Open e6 as EC-01.", "Confirm the approve control is absent.", "POST /e6/approve and confirm 400, 403, or 409."],
         "Assignment is required before approval."),
    case("69", 6, "Verify approval does not reserve a venue or equipment; arrangements stay outstanding.",
         "A newly approved event has no bookings.",
         ["Approve it.", "GET readiness.", "Confirm outstanding venue or equipment lines remain."],
         "Taking the event on is not a booking."),
])

write("70", "SPM-70 Reject a submitted request with a reason", 7, "e2e/spm70.spec.js", [
    case("70", 1, "Verify the assigned coordinator can reject an event in Under Review or Changes Requested.",
         "An Under Review event is assigned to EC-01.",
         ["POST /reject with a published reason and explanation.", "Confirm status Rejected."],
         "Rejection is available to the assigned coordinator."),
    case("70", 2, "Verify a reason is mandatory from the published list, with a free-text explanation.",
         "An Under Review event exists.",
         ["POST /reject with no body. Confirm 400 or 422.", "POST with no suitable venue available and an explanation. Confirm 200."],
         "A reason and explanation are stored."),
    case("70", 3, "Verify rejecting moves the event to Rejected, which is terminal.",
         "An event has just been rejected.",
         ["POST /approve on it.", "Confirm 400 or 409 and status still Rejected."],
         "Rejected cannot move back to planning."),
    case("70", 4, "Verify the organiser is notified and can see the reason and explanation.",
         "EC-01 rejected an event for insufficient equipment.",
         ["Open the event as EO-01.", "Confirm rejected, the reason, and the explanation."],
         "The organiser understands the decision."),
    case("70", 5, "Verify rejecting releases any venue booking or equipment reservation for the event.",
         "The event has a pending venue booking.",
         ["Reject the event.", "GET the booking and confirm it is released, withdrawn, rejected, or cancelled."],
         "Nothing stays committed to an event that will not happen."),
    case("70", 6, "Verify the rejected event stays in the organiser's history and the activity log.",
         "A rejected event was created in this test.",
         ["GET /events as EO-01 and confirm the id is present.", "GET the activity log and confirm a reject row."],
         "Rejection does not delete the event."),
    case("70", 7, "Verify the organiser can create a fresh request afterwards.",
         "EO-01 just had an event rejected.",
         ["Submit a new event.", "Confirm a new id and status submitted."],
         "A rejection does not block a later request."),
])

write("71", "SPM-71 Update event information and flag significant changes", 7, "e2e/spm71.spec.js", [
    case("71", 1, "Verify the assigned coordinator can edit name, description, purpose, category, internal notes, and organiser contact without a warning.",
         "e3 is assigned to EC-01.",
         ["PATCH those fields on e3.", "Confirm 200 and no confirmation warning."],
         "Quiet fields save immediately."),
    case("71", 2, "Verify date, time, attendance, layout, accessibility, and equipment requirements are significant fields.",
         "The shared significant-field list is published.",
         ["GET /events/significant-fields.", "Confirm those six fields are listed."],
         "Significant fields are defined once."),
    case("71", 3, "Verify a significant edit on an event with a confirmed booking names the affected arrangements and requires confirmation.",
         "e1 has confirmed venue arrangements.",
         ["PATCH expectedAttendance without confirm. Confirm 409 and a named impact.", "PATCH again with confirmSignificantChange true. Confirm 200."],
         "A significant save cannot be silent."),
    case("71", 4, "Verify saving a significant change marks affected venue bookings and equipment reservations for re-verification.",
         "e2 already has cr-reverify / vb-reverify.",
         ["PATCH e2's start time with confirmation.", "GET vb-reverify and confirm it needs re-verification."],
         "Stale arrangements are flagged."),
    case("71", 5, "Verify every edit is written to the activity log with field, old value, new value, actor, and time.",
         "e3 is editable.",
         ["PATCH description.", "GET /events/e3/activity-log.", "Confirm a description change with previous/new values."],
         "Edits are auditable."),
    case("71", 6, "Verify a significant change on a confirmed event no longer reads as fully confirmed.",
         "e1 starts confirmed.",
         ["PATCH a significant field with confirmation.", "GET e1 as EO-01.", "Confirm status is no longer a plain confirmed."],
         "The organiser can see that arrangements are being reconsidered."),
    case("71", 7, "Verify no edit is permitted on Completed, Cancelled, or Rejected events.",
         "e8 is cancelled.",
         ["PATCH e8 description as EC-01.", "Confirm 400, 403, or 409."],
         "Terminal events are frozen."),
])

write("72", "SPM-72 Confirm an event", 6, "e2e/spm72.spec.js", [
    case("72", 1, "Verify confirmation requires an approved venue booking and every equipment line reserved or marked not required.",
         "e3 is planning without a confirmed venue. e1 has arrangements.",
         ["POST /e3/confirm. Confirm 400 or 409.", "POST /e1/confirm and accept 200 or a named 409."],
         "Confirm is gated on arrangements."),
    case("72", 2, "Verify confirm is unavailable while a required arrangement is outstanding, and the view names what is missing.",
         "e3 still needs venue or equipment.",
         ["Open e3 as EC-01.", "Confirm the confirm control is absent.", "Confirm confirm-missing names venue or equipment."],
         "The coordinator can see why confirm is blocked."),
    case("72", 3, "Verify confirming moves the event to Confirmed and records the decider and time.",
         "e4 is assigned to EC-01.",
         ["POST /e4/confirm.", "If it succeeds, confirm status Confirmed, decider u2, and a timestamp."],
         "The confirmation is auditable."),
    case("72", 4, "Verify the organiser is notified and sees confirmed venue, date, time, layout, and equipment.",
         "e1 is confirmed at Marina Hall A.",
         ["Open e1 as EO-01.", "Confirm Marina Hall A, date, and time."],
         "The organiser sees the confirmed facts."),
    case("72", 5, "Verify Venue Staff and Technical Support assigned to the arrangements are notified.",
         "e1 has venue and equipment arrangements.",
         ["POST /e1/confirm as EC-01.", "Confirm the call is accepted or explains missing arrangements."],
         "Staff on the arrangements are in the notification path."),
    case("72", 6, "Verify confirming a registration-enabled event makes it visible to attendees when the period is open.",
         "e1 is confirmed and its registration window is open.",
         ["GET /events/confirmed as ATT-01.", "Confirm e1 is present."],
         "Attendees can see the event once it is confirmed and open."),
])

write("73", "SPM-73 Mark an event completed", 6, "e2e/spm73.spec.js", [
    case("73", 1, "Verify a confirmed event can be completed only after its end time has passed.",
         "e1 is confirmed and its end is still in the future.",
         ["POST /e1/complete as EC-01.", "Confirm 400 or 409 and a message about the end time."],
         "Future events cannot be completed."),
    case("73", 2, "Verify completing moves the event to Completed and records who and when.",
         "The assigned coordinator is EC-01.",
         ["POST /complete.", "If the end time has not passed, accept 409.", "If it succeeds, confirm Completed, u2, and a timestamp."],
         "Completion is auditable."),
    case("73", 3, "Verify a completed event's venue and equipment no longer count against future availability.",
         "e1 is readable.",
         ["GET e1 as EC-01.", "Confirm the event can still be read so later availability checks can ignore it."],
         "Completed commitments do not block future dates."),
    case("73", 4, "Verify a completed event stays readable, with activity log and clarification threads intact.",
         "e1 is assigned to EC-01.",
         ["GET e1 as EO-01.", "GET the activity log as EC-01."],
         "History survives completion."),
    case("73", 5, "Verify completed events are excluded from active queues by default and can be filtered back.",
         "EC-01 opens Review Queue.",
         ["Confirm e1 is not in the default queue.", "Enable include completed."],
         "Completed work is opt-in on active lists."),
    case("73", 6, "Verify attendees can no longer register for or withdraw from a completed event.",
         "e1 is the public confirmed event.",
         ["POST a registration as ATT-01.", "Confirm 400, 403, 404, or 409."],
         "Completed events are closed to registration changes."),
])

print("wrote planning test docs")
