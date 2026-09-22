# Acceptance-Test Traceability

| Story | Acceptance criterion | Test case | Spec | Automation |
|---|---|---|---|---|
| SPM-43 | Valid login reaches role home | TC-SPM43-AC01 | `e2e/spm43.spec.js` | Automated |
| SPM-43 | Valid login creates session | TC-SPM43-AC02 | `e2e/spm43.spec.js` | Automated |
| SPM-43 | Invalid login is generic / no session | TC-SPM43-AC03 | `e2e/spm43.spec.js` | Automated |
| SPM-43 | Empty fields block submit | TC-SPM43-AC04 | `e2e/spm43.spec.js` | Automated |
| SPM-43 | Protected page / API requires session | TC-SPM43-AC05 | `e2e/spm43.spec.js` | Automated |
| SPM-43 | Logout prevents Back access | TC-SPM43-AC06 | `e2e/spm43.spec.js` | Automated |
| SPM-43 | Password is masked | TC-SPM43-AC07 | `e2e/spm43.spec.js` | Automated |
| SPM-45 | Venue Staff permissions | TC-SPM45-AC01 | `e2e/spm45-api.spec.js`; `e2e/spm45-ui.contract.spec.js` | API automated; UI skipped |
| SPM-45 | Technical Support permissions | TC-SPM45-AC02 | `e2e/spm45-api.spec.js`; `e2e/spm45-ui.contract.spec.js` | API automated; UI skipped |
| SPM-45 | Event Coordinator permissions | TC-SPM45-AC03 | `e2e/spm45-api.spec.js`; `e2e/spm45-ui.contract.spec.js` | API automated; UI skipped |
| SPM-45 | Wrong-role action returns 403 | TC-SPM45-AC04 | `e2e/spm45-api.spec.js`; `e2e/spm45-ui.contract.spec.js` | API automated; UI skipped |
| SPM-46 | Assigned coordinator can act | TC-SPM46-AC01 | `e2e/spm46-api.spec.js`; `e2e/spm46-ui.contract.spec.js` | API role checks automated; assignment-gate and UI skipped |
| SPM-46 | Unassigned staff read-only | TC-SPM46-AC02 | `e2e/spm46-api.spec.js`; `e2e/spm46-ui.contract.spec.js` | API read automated; UI skipped |
| SPM-46 | Reassignment swaps permissions | TC-SPM46-AC03 | `e2e/spm46-api.spec.js`; `e2e/spm46-ui.contract.spec.js` | Assignment write automated; revoke/grant and UI skipped |
| SPM-47 | Organiser list is org-scoped | TC-SPM47-AC01 | `e2e/spm47-api.spec.js`; `e2e/spm47-ui.contract.spec.js` | Automated |
| SPM-47 | Cross-org event URL/API rejected | TC-SPM47-AC02 | `e2e/spm47-api.spec.js`; `e2e/spm47-ui.contract.spec.js` | Automated |
| SPM-47 | Attendee public overview and own registrations | TC-SPM47-AC03 | `e2e/spm47-api.spec.js`; `e2e/spm47-ui.contract.spec.js` | Automated |
| SPM-55 | Unassigned submitted requests with wait time | TC-SPM55-AC01 | `e2e/spm55.spec.js` | Automated |
| SPM-55 | Assigned events with status and outstanding work | TC-SPM55-AC02 | `e2e/spm55.spec.js` | Automated |
| SPM-55 | Pending change requests newest first | TC-SPM55-AC03 | `e2e/spm55.spec.js` | Automated |
| SPM-55 | Re-verification items shown prominently | TC-SPM55-AC04 | `e2e/spm55.spec.js` | Automated |
| SPM-55 | Items link to the work screen | TC-SPM55-AC05 | `e2e/spm55.spec.js` | Automated |
| SPM-55 | Lists obey coordinator access rules | TC-SPM55-AC06 | `e2e/spm55.spec.js` | Automated |
| SPM-55 | Empty states say there is nothing to do | TC-SPM55-AC07 | `e2e/spm55.spec.js` | Automated |
| SPM-56 | Open clarifications shown first | TC-SPM56-AC01 | `e2e/spm56.spec.js` | Automated |
| SPM-56 | Events grouped by plain-language stage | TC-SPM56-AC02 | `e2e/spm56.spec.js` | Automated |
| SPM-56 | Pending change requests and outcomes | TC-SPM56-AC03 | `e2e/spm56.spec.js` | Automated |
| SPM-56 | Confirmed events show venue, date, time | TC-SPM56-AC04 | `e2e/spm56.spec.js` | Automated |
| SPM-56 | New event request from the dashboard | TC-SPM56-AC05 | `e2e/spm56.spec.js` | Automated |
| SPM-56 | Org-scoped list including colleagues, server enforced | TC-SPM56-AC06 | `e2e/spm56.spec.js` | Automated |
| SPM-56 | Empty states and first-request prompt | TC-SPM56-AC07 | `e2e/spm56.spec.js` | Automated |
| SPM-57 | Pending booking requests with event, venue, datetime | TC-SPM57-AC01 | `e2e/spm57.spec.js` | Automated |
| SPM-57 | Bookings flagged for re-verification | TC-SPM57-AC02 | `e2e/spm57.spec.js` | Automated |
| SPM-57 | Confirmed bookings in the next few days | TC-SPM57-AC03 | `e2e/spm57.spec.js` | Automated |
| SPM-57 | Items link to the work screen | TC-SPM57-AC04 | `e2e/spm57.spec.js` | Automated |
| SPM-57 | Lists obey venue access rules | TC-SPM57-AC05 | `e2e/spm57.spec.js` | Automated |
| SPM-57 | Each section has an empty state | TC-SPM57-AC06 | `e2e/spm57.spec.js` | Automated |
| SPM-58 | Equipment requests awaiting review | TC-SPM58-AC01 | `e2e/spm58.spec.js` | Automated |
| SPM-58 | Reservations flagged for re-verification | TC-SPM58-AC02 | `e2e/spm58.spec.js` | Automated |
| SPM-58 | Unresolved unavailable or shortfall lines | TC-SPM58-AC03 | `e2e/spm58.spec.js` | Automated |
| SPM-58 | Upcoming supplied events soonest first | TC-SPM58-AC04 | `e2e/spm58.spec.js` | Automated |
| SPM-58 | Items link to the work screen | TC-SPM58-AC05 | `e2e/spm58.spec.js` | Automated |
| SPM-58 | Lists obey technical-support access rules | TC-SPM58-AC06 | `e2e/spm58.spec.js` | Automated |
| SPM-58 | Each section has an empty state | TC-SPM58-AC07 | `e2e/spm58.spec.js` | Automated |
| SPM-59 | Next upcoming registration first | TC-SPM59-AC01 | `e2e/spm59.spec.js` | Automated |
| SPM-59 | Changed event flagged | TC-SPM59-AC02 | `e2e/spm59.spec.js` | Automated |
| SPM-59 | Cancelled registration shown as cancelled | TC-SPM59-AC03 | `e2e/spm59.spec.js` | Automated |
| SPM-59 | Open events beneath own registrations | TC-SPM59-AC04 | `e2e/spm59.spec.js` | Automated |
| SPM-59 | No coordinator, notes, or other attendees | TC-SPM59-AC05 | `e2e/spm59.spec.js` | Automated |
| SPM-59 | No registrations points at browsing events | TC-SPM59-AC06 | `e2e/spm59.spec.js` | Automated |
| SPM-8 | View submitted request and approve | TC-SPM08-AC01 | `e2e/spm08.spec.js` | Automated |
| SPM-8 | Approved booking reserved by datetime | TC-SPM08-AC02 | `e2e/spm08.spec.js` | Automated |
| SPM-8 | Approved booking locked until event completes | TC-SPM08-AC03 | `e2e/spm08.spec.js` | Automated |
| SPM-8 | Approver and time persist | TC-SPM08-AC04 | `e2e/spm08.spec.js` | Automated |
| SPM-8 | Unavailability blocks approval | TC-SPM08-AC05 | `e2e/spm08.spec.js` | Automated |
| SPM-8 | Confirmed overlap blocks approval | TC-SPM08-AC06 | `e2e/spm08.spec.js` | Automated |
| SPM-8 | Tentative hold blocks approval | TC-SPM08-AC07 | `e2e/spm08.spec.js` | Automated |
| SPM-8 | Free slot becomes confirmed and locks venue | TC-SPM08-AC08 | `e2e/spm08.spec.js` | Automated |
| SPM-8 | Competing requests oldest first | TC-SPM08-AC09 | `e2e/spm08.spec.js` | Automated |
| SPM-9 | Record unavailability period | TC-SPM09-AC01 | `e2e/spm09.spec.js` | Automated |
| SPM-9 | Mandatory reason from published list | TC-SPM09-AC02 | `e2e/spm09.spec.js` | Automated |
| SPM-9 | Block excludes venue from search | TC-SPM09-AC03 | `e2e/spm09.spec.js` | Automated |
| SPM-9 | Block prevents overlapping approval | TC-SPM09-AC04 | `e2e/spm09.spec.js` | Automated |
| SPM-9 | Calendar shows Unavailable | TC-SPM09-AC05 | `e2e/spm09.spec.js` | Automated |
| SPM-9 | Overlap warning, acknowledge, notify | TC-SPM09-AC06 | `e2e/spm09.spec.js` | Automated |
| SPM-9 | Cancel block frees the slot | TC-SPM09-AC07 | `e2e/spm09.spec.js` | Automated |
| SPM-9 | Unavailability changes in activity log | TC-SPM09-AC08 | `e2e/spm09.spec.js` | Automated |
| SPM-10 | View pending request details | TC-SPM10-AC01 | `e2e/spm10.spec.js` | Automated |
| SPM-10 | Reject requires a reason | TC-SPM10-AC02 | `e2e/spm10.spec.js` | Automated |
| SPM-10 | Optional alternative venue | TC-SPM10-AC03 | `e2e/spm10.spec.js` | Automated |
| SPM-10 | Rejected leaves queue and is read-only | TC-SPM10-AC04 | `e2e/spm10.spec.js` | Automated |
| SPM-10 | Rejected request holds nothing | TC-SPM10-AC05 | `e2e/spm10.spec.js` | Automated |
| SPM-10 | Rejecter, reason, and time recorded | TC-SPM10-AC06 | `e2e/spm10.spec.js` | Automated |
| SPM-10 | Pending requests do not auto-expire | TC-SPM10-AC07 | `e2e/spm10.spec.js` | Automated |
| SPM-17 | Staff list name, location, capacity | TC-SPM17-AC01 | `e2e/spm17.spec.js` | Automated |
| SPM-17 | Venue detail fields | TC-SPM17-AC02 | `e2e/spm17.spec.js` | Automated |
| SPM-17 | Retired hidden unless filtered | TC-SPM17-AC03 | `e2e/spm17.spec.js` | Automated |
| SPM-17 | Open venue calendar from catalogue | TC-SPM17-AC04 | `e2e/spm17.spec.js` | Automated |
| SPM-17 | Organiser and attendee blocked on server | TC-SPM17-AC05 | `e2e/spm17.spec.js` | Automated |
| SPM-17 | Empty catalogue copy | TC-SPM17-AC06 | `e2e/spm17.spec.js` | Automated |
| SPM-60 | Venue record fields | TC-SPM60-AC01 | `e2e/spm60.spec.js` | Automated |
| SPM-60 | Layouts with capacity | TC-SPM60-AC02 | `e2e/spm60.spec.js` | Automated |
| SPM-60 | Capacity from highest layout | TC-SPM60-AC03 | `e2e/spm60.spec.js` | Automated |
| SPM-60 | Add, edit, retire without deleting history | TC-SPM60-AC04 | `e2e/spm60.spec.js` | Automated |
| SPM-60 | Retire warns on future confirmed bookings | TC-SPM60-AC05 | `e2e/spm60.spec.js` | Automated |
| SPM-60 | Zero or negative layout capacity rejected | TC-SPM60-AC06 | `e2e/spm60.spec.js` | Automated |
| SPM-60 | Only venue staff can write | TC-SPM60-AC07 | `e2e/spm60.spec.js` | Automated |
| SPM-60 | Seeded published catalogue | TC-SPM60-AC08 | `e2e/spm60.spec.js` | Automated |
| SPM-60 | Changes written to activity log | TC-SPM60-AC09 | `e2e/spm60.spec.js` | Automated |
| SPM-61 | Search pre-filled from event | TC-SPM61-AC01 | `e2e/spm61.spec.js` | Automated |
| SPM-61 | Published filters | TC-SPM61-AC02 | `e2e/spm61.spec.js` | Automated |
| SPM-61 | Confirmed or unavailable excluded | TC-SPM61-AC03 | `e2e/spm61.spec.js` | Automated |
| SPM-61 | Layout or capacity mismatch excluded | TC-SPM61-AC04 | `e2e/spm61.spec.js` | Automated |
| SPM-61 | Missing facility or access excluded | TC-SPM61-AC05 | `e2e/spm61.spec.js` | Automated |
| SPM-61 | Outside hours excluded | TC-SPM61-AC06 | `e2e/spm61.spec.js` | Automated |
| SPM-61 | Layout capacity and headroom | TC-SPM61-AC07 | `e2e/spm61.spec.js` | Automated |
| SPM-61 | Pending overlap marked contested | TC-SPM61-AC08 | `e2e/spm61.spec.js` | Automated |
| SPM-62 | Verdict with reasons | TC-SPM62-AC01 | `e2e/spm62.spec.js` | Automated |
| SPM-62 | Over-capacity names both numbers | TC-SPM62-AC02 | `e2e/spm62.spec.js` | Automated |
| SPM-62 | Missing layout, facility, access | TC-SPM62-AC03 | `e2e/spm62.spec.js` | Automated |
| SPM-62 | Clash named as failure | TC-SPM62-AC04 | `e2e/spm62.spec.js` | Automated |
| SPM-62 | Outside hours is a failure | TC-SPM62-AC05 | `e2e/spm62.spec.js` | Automated |
| SPM-62 | Tight fit is a warning | TC-SPM62-AC06 | `e2e/spm62.spec.js` | Automated |
| SPM-62 | Pending overlap is a warning | TC-SPM62-AC07 | `e2e/spm62.spec.js` | Automated |
| SPM-62 | Failures block submit; warnings do not | TC-SPM62-AC08 | `e2e/spm62.spec.js` | Automated |
| SPM-62 | Shared suitability rule | TC-SPM62-AC09 | `e2e/spm62.spec.js` | Automated |
| SPM-63 | Request venue for planning event | TC-SPM63-AC01 | `e2e/spm63.spec.js` | Automated |
| SPM-63 | Request carries event facts | TC-SPM63-AC02 | `e2e/spm63.spec.js` | Automated |
| SPM-63 | Failed suitability blocks submit | TC-SPM63-AC03 | `e2e/spm63.spec.js` | Automated |
| SPM-63 | Warnings acknowledged and carried | TC-SPM63-AC04 | `e2e/spm63.spec.js` | Automated |
| SPM-63 | Notify staff and pending queue | TC-SPM63-AC05 | `e2e/spm63.spec.js` | Automated |
| SPM-63 | Pending on calendar, not locking | TC-SPM63-AC06 | `e2e/spm63.spec.js` | Automated |
| SPM-63 | One pending request per event | TC-SPM63-AC07 | `e2e/spm63.spec.js` | Automated |
| SPM-63 | Coordinator can withdraw | TC-SPM63-AC08 | `e2e/spm63.spec.js` | Automated |
| SPM-63 | Readiness in progress while pending | TC-SPM63-AC09 | `e2e/spm63.spec.js` | Automated |
| SPM-64 | Shared conflict rule | TC-SPM64-AC01 | `e2e/spm64.spec.js` | Automated |
| SPM-64 | Confirmed bookings never overlap | TC-SPM64-AC02 | `e2e/spm64.spec.js` | Automated |
| SPM-64 | Booking conflicts with unavailability | TC-SPM64-AC03 | `e2e/spm64.spec.js` | Automated |
| SPM-64 | Touching ranges allowed | TC-SPM64-AC04 | `e2e/spm64.spec.js` | Automated |
| SPM-64 | Simultaneous approve: one winner | TC-SPM64-AC05 | `e2e/spm64.spec.js` | Automated |
| SPM-64 | Release hold on reject or withdraw | TC-SPM64-AC06 | `e2e/spm64.spec.js` | Automated |
| SPM-64 | Overlap boundary cases | TC-SPM64-AC07 | `e2e/spm64.spec.js` | Automated |
| SPM-108 | Calendar shows all three kinds | TC-SPM108-AC01 | `e2e/spm108.spec.js` | Automated |
| SPM-108 | Kinds are visually distinct | TC-SPM108-AC02 | `e2e/spm108.spec.js` | Automated |
| SPM-108 | Entry shows name, org, time, and opens | TC-SPM108-AC03 | `e2e/spm108.spec.js` | Automated |
| SPM-108 | Outside hours shown unavailable | TC-SPM108-AC04 | `e2e/spm108.spec.js` | Automated |
| SPM-108 | Week, month, and past ranges | TC-SPM108-AC05 | `e2e/spm108.spec.js` | Automated |
| SPM-108 | Next open reflects new decision | TC-SPM108-AC06 | `e2e/spm108.spec.js` | Automated |
| SPM-108 | Internal roles can read any calendar | TC-SPM108-AC07 | `e2e/spm108.spec.js` | Automated |
| SPM-108 | Empty range is not an error | TC-SPM108-AC08 | `e2e/spm108.spec.js` | Automated |
| SPM-5 | Readiness table columns | TC-SPM05-AC01 | `e2e/spm05.spec.js` | Automated |
| SPM-5 | Update readiness status | TC-SPM05-AC02 | `e2e/spm05.spec.js` | Automated |
| SPM-5 | Assigned personnel contact | TC-SPM05-AC03 | `e2e/spm05.spec.js` | Automated |
| SPM-5 | View supporting attachments | TC-SPM05-AC04 | `e2e/spm05.spec.js` | Automated |
| SPM-5 | Create, modify, and delete a line item | TC-SPM05-AC05 | `e2e/spm05.spec.js` | Automated |
| SPM-5 | Saved line-item information persists | TC-SPM05-AC06 | `e2e/spm05.spec.js` | Automated |
| SPM-5 | Confirmation on status | TC-SPM05-AC07 | `e2e/spm05.spec.js` | Automated |
| SPM-5 | Near-due line items are alerted | TC-SPM05-AC08 | `e2e/spm05.spec.js` | Automated |
| SPM-5 | Overdue line items are flagged | TC-SPM05-AC09 | `e2e/spm05.spec.js` | Automated |
| SPM-15 | Organisation events with status and date | TC-SPM15-AC01 | `e2e/spm15.spec.js` | Automated |
| SPM-15 | Drafts distinguishable from submitted | TC-SPM15-AC02 | `e2e/spm15.spec.js` | Automated |
| SPM-15 | Arrangements in plain language | TC-SPM15-AC03 | `e2e/spm15.spec.js` | Automated |
| SPM-15 | Needs-action items flagged and linked | TC-SPM15-AC04 | `e2e/spm15.spec.js` | Automated |
| SPM-15 | Assigned coordinator name and contact | TC-SPM15-AC05 | `e2e/spm15.spec.js` | Automated |
| SPM-15 | Confirmed venue, date, time, layout, equipment | TC-SPM15-AC06 | `e2e/spm15.spec.js` | Automated |
| SPM-15 | Shown status matches stored status | TC-SPM15-AC07 | `e2e/spm15.spec.js` | Automated |
| SPM-15 | No internal notes or other clients | TC-SPM15-AC08 | `e2e/spm15.spec.js` | Automated |
| SPM-15 | Empty state points at creating a request | TC-SPM15-AC09 | `e2e/spm15.spec.js` | Automated |
| SPM-65 | Queue statuses exclude drafts | TC-SPM65-AC01 | `e2e/spm65.spec.js` | Automated |
| SPM-65 | Queue row fields | TC-SPM65-AC02 | `e2e/spm65.spec.js` | Automated |
| SPM-65 | Unassigned distinguished and filterable | TC-SPM65-AC03 | `e2e/spm65.spec.js` | Automated |
| SPM-65 | Sort by wait and proposed date | TC-SPM65-AC04 | `e2e/spm65.spec.js` | Automated |
| SPM-65 | Filter to assigned-to-me | TC-SPM65-AC05 | `e2e/spm65.spec.js` | Automated |
| SPM-65 | Near proposed date uses shared threshold | TC-SPM65-AC06 | `e2e/spm65.spec.js` | Automated |
| SPM-65 | Empty filter explains the exclusion | TC-SPM65-AC07 | `e2e/spm65.spec.js` | Automated |
| SPM-66 | Assign self or another coordinator | TC-SPM66-AC01 | `e2e/spm66.spec.js` | Automated |
| SPM-66 | Candidate list shows active-event counts | TC-SPM66-AC02 | `e2e/spm66.spec.js` | Automated |
| SPM-66 | No workload cap | TC-SPM66-AC03 | `e2e/spm66.spec.js` | Automated |
| SPM-66 | Assignment recorded in the activity log | TC-SPM66-AC04 | `e2e/spm66.spec.js` | Automated |
| SPM-66 | Notify and show coordinator contact | TC-SPM66-AC05 | `e2e/spm66.spec.js` | Automated |
| SPM-66 | Submitted moves to Under Review | TC-SPM66-AC06 | `e2e/spm66.spec.js` | Automated |
| SPM-66 | Non-coordinators get 403 | TC-SPM66-AC07 | `e2e/spm66.spec.js` | Automated |
| SPM-66 | Cannot assign a non-coordinator | TC-SPM66-AC08 | `e2e/spm66.spec.js` | Automated |
| SPM-68 | Raise a clarification with optional field | TC-SPM68-AC01 | `e2e/spm68.spec.js` | Automated |
| SPM-68 | Event moves to Changes Requested | TC-SPM68-AC02 | `e2e/spm68.spec.js` | Automated |
| SPM-68 | Thread shows author, role, and time | TC-SPM68-AC03 | `e2e/spm68.spec.js` | Automated |
| SPM-68 | Multiple clarifications stay independent | TC-SPM68-AC04 | `e2e/spm68.spec.js` | Automated |
| SPM-68 | All resolved returns Under Review | TC-SPM68-AC05 | `e2e/spm68.spec.js` | Automated |
| SPM-68 | Attendees cannot see threads | TC-SPM68-AC06 | `e2e/spm68.spec.js` | Automated |
| SPM-68 | Threads remain after later statuses | TC-SPM68-AC07 | `e2e/spm68.spec.js` | Automated |
| SPM-68 | Drafts cannot receive a clarification | TC-SPM68-AC08 | `e2e/spm68.spec.js` | Automated |
| SPM-69 | Assigned coordinator can approve with a note | TC-SPM69-AC01 | `e2e/spm69.spec.js` | Automated |
| SPM-69 | Approval records decider and time | TC-SPM69-AC02 | `e2e/spm69.spec.js` | Automated |
| SPM-69 | Organiser sees approval outcome | TC-SPM69-AC03 | `e2e/spm69.spec.js` | Automated |
| SPM-69 | Open clarifications warn and require confirm | TC-SPM69-AC04 | `e2e/spm69.spec.js` | Automated |
| SPM-69 | Unassigned submitted cannot be approved | TC-SPM69-AC05 | `e2e/spm69.spec.js` | Automated |
| SPM-69 | Approval does not reserve arrangements | TC-SPM69-AC06 | `e2e/spm69.spec.js` | Automated |
| SPM-70 | Assigned coordinator can reject | TC-SPM70-AC01 | `e2e/spm70.spec.js` | Automated |
| SPM-70 | Mandatory reason and explanation | TC-SPM70-AC02 | `e2e/spm70.spec.js` | Automated |
| SPM-70 | Rejected is terminal | TC-SPM70-AC03 | `e2e/spm70.spec.js` | Automated |
| SPM-70 | Organiser sees reason and explanation | TC-SPM70-AC04 | `e2e/spm70.spec.js` | Automated |
| SPM-70 | Rejecting releases holds | TC-SPM70-AC05 | `e2e/spm70.spec.js` | Automated |
| SPM-70 | Rejected event stays in history | TC-SPM70-AC06 | `e2e/spm70.spec.js` | Automated |
| SPM-70 | Organiser can submit a fresh request | TC-SPM70-AC07 | `e2e/spm70.spec.js` | Automated |
| SPM-71 | Quiet fields save without warning | TC-SPM71-AC01 | `e2e/spm71.spec.js` | Automated |
| SPM-71 | Significant fields are published | TC-SPM71-AC02 | `e2e/spm71.spec.js` | Automated |
| SPM-71 | Significant edit requires confirmation | TC-SPM71-AC03 | `e2e/spm71.spec.js` | Automated |
| SPM-71 | Affected arrangements marked for re-verification | TC-SPM71-AC04 | `e2e/spm71.spec.js` | Automated |
| SPM-71 | Edits written to the activity log | TC-SPM71-AC05 | `e2e/spm71.spec.js` | Automated |
| SPM-71 | Confirmed event no longer reads fully confirmed | TC-SPM71-AC06 | `e2e/spm71.spec.js` | Automated |
| SPM-71 | Terminal events cannot be edited | TC-SPM71-AC07 | `e2e/spm71.spec.js` | Automated |
| SPM-72 | Confirm gated on venue and equipment | TC-SPM72-AC01 | `e2e/spm72.spec.js` | Automated |
| SPM-72 | Outstanding arrangements named | TC-SPM72-AC02 | `e2e/spm72.spec.js` | Automated |
| SPM-72 | Confirm records decider and time | TC-SPM72-AC03 | `e2e/spm72.spec.js` | Automated |
| SPM-72 | Organiser sees confirmed arrangements | TC-SPM72-AC04 | `e2e/spm72.spec.js` | Automated |
| SPM-72 | Assigned staff are notified | TC-SPM72-AC05 | `e2e/spm72.spec.js` | Automated |
| SPM-72 | Confirmed open events visible to attendees | TC-SPM72-AC06 | `e2e/spm72.spec.js` | Automated |
| SPM-73 | Complete only after end time | TC-SPM73-AC01 | `e2e/spm73.spec.js` | Automated |
| SPM-73 | Completion records who and when | TC-SPM73-AC02 | `e2e/spm73.spec.js` | Automated |
| SPM-73 | Completed holds leave future availability | TC-SPM73-AC03 | `e2e/spm73.spec.js` | Automated |
| SPM-73 | History stays readable | TC-SPM73-AC04 | `e2e/spm73.spec.js` | Automated |
| SPM-73 | Completed excluded from active queues | TC-SPM73-AC05 | `e2e/spm73.spec.js` | Automated |
| SPM-73 | Attendees cannot register or withdraw | TC-SPM73-AC06 | `e2e/spm73.spec.js` | Automated |
| SPM-2 | Requested and available quantity per line | TC-SPM02-AC01 | `e2e/spm02.spec.js` | Automated |
| SPM-2 | Overlapping reservations excluded | TC-SPM02-AC02 | `e2e/spm02.spec.js` | Automated |
| SPM-2 | Out-of-service units excluded | TC-SPM02-AC03 | `e2e/spm02.spec.js` | Automated |
| SPM-2 | Whole-request verdict and named shortfalls | TC-SPM02-AC04 | `e2e/spm02.spec.js` | Automated |
| SPM-2 | Shortfall names overlapping events | TC-SPM02-AC05 | `e2e/spm02.spec.js` | Automated |
| SPM-2 | Touching periods do not compete | TC-SPM02-AC06 | `e2e/spm02.spec.js` | Automated |
| SPM-2 | Re-check after reserve or release | TC-SPM02-AC07 | `e2e/spm02.spec.js` | Automated |
| SPM-2 | Check is read-only | TC-SPM02-AC08 | `e2e/spm02.spec.js` | Automated |
| SPM-2 | Exact fit, shortfall of one, overlap, OOS, touching | TC-SPM02-AC09 | `e2e/spm02.spec.js` | Automated |
| SPM-3 | Reserve up to available quantity | TC-SPM03-AC01 | `e2e/spm03.spec.js` | Automated |
| SPM-3 | Excess quantity refused | TC-SPM03-AC02 | `e2e/spm03.spec.js` | Automated |
| SPM-3 | Reservation reduces overlapping availability | TC-SPM03-AC03 | `e2e/spm03.spec.js` | Automated |
| SPM-3 | Out-of-service units cannot be reserved | TC-SPM03-AC04 | `e2e/spm03.spec.js` | Automated |
| SPM-3 | Simultaneous last-unit race | TC-SPM03-AC05 | `e2e/spm03.spec.js` | Automated |
| SPM-3 | Reservation visible on event and type | TC-SPM03-AC06 | `e2e/spm03.spec.js` | Automated |
| SPM-3 | Coordinator sees full reservation | TC-SPM03-AC07 | `e2e/spm03.spec.js` | Automated |
| SPM-3 | Event end-states release reservations | TC-SPM03-AC08 | `e2e/spm03.spec.js` | Automated |
| SPM-3 | Reserve and release in the activity log | TC-SPM03-AC09 | `e2e/spm03.spec.js` | Automated |
| SPM-3 | Full reserve marks equipment ready | TC-SPM03-AC10 | `e2e/spm03.spec.js` | Automated |
| SPM-4 | Upcoming equipment events, soonest first | TC-SPM04-AC01 | `e2e/spm04.spec.js` | Automated |
| SPM-4 | Queue row fields | TC-SPM04-AC02 | `e2e/spm04.spec.js` | Automated |
| SPM-4 | Review, partial, reserved, or unavailable | TC-SPM04-AC03 | `e2e/spm04.spec.js` | Automated |
| SPM-4 | Attention and re-verification first on a date | TC-SPM04-AC04 | `e2e/spm04.spec.js` | Automated |
| SPM-4 | Status and date filters; terminal events excluded | TC-SPM04-AC05 | `e2e/spm04.spec.js` | Automated |
| SPM-4 | No-requirement events excluded | TC-SPM04-AC06 | `e2e/spm04.spec.js` | Automated |
| SPM-4 | Open event to check and reserve | TC-SPM04-AC07 | `e2e/spm04.spec.js` | Automated |
| SPM-75 | Catalogue record fields | TC-SPM75-AC01 | `e2e/spm75.spec.js` | Automated |
| SPM-75 | Out-of-service counts by reason | TC-SPM75-AC02 | `e2e/spm75.spec.js` | Automated |
| SPM-75 | Available = owned − OOS − overlapping | TC-SPM75-AC03 | `e2e/spm75.spec.js` | Automated |
| SPM-75 | Writes are technical-support only | TC-SPM75-AC04 | `e2e/spm75.spec.js` | Automated |
| SPM-75 | Out-of-service above total rejected | TC-SPM75-AC05 | `e2e/spm75.spec.js` | Automated |
| SPM-75 | OOS below reserved requires acknowledgement | TC-SPM75-AC06 | `e2e/spm75.spec.js` | Automated |
| SPM-75 | Quantity changes in the activity log | TC-SPM75-AC07 | `e2e/spm75.spec.js` | Automated |
| SPM-76 | Request captures type, quantity, and notes | TC-SPM76-AC01 | `e2e/spm76.spec.js` | Automated |
| SPM-76 | Only technical support can reserve or mark unavailable | TC-SPM76-AC02 | `e2e/spm76.spec.js` | Automated |
| SPM-76 | Last updater and time stored | TC-SPM76-AC03 | `e2e/spm76.spec.js` | Automated |
| SPM-76 | Unfulfillable line notifies the coordinator | TC-SPM76-AC04 | `e2e/spm76.spec.js` | Automated |
| SPM-77 | Mark a line unavailable with alternative | TC-SPM77-AC01 | `e2e/spm77.spec.js` | Automated |
| SPM-77 | Partly fulfil and state the shortfall | TC-SPM77-AC02 | `e2e/spm77.spec.js` | Automated |
| SPM-77 | Coordinator notified of shortfall | TC-SPM77-AC03 | `e2e/spm77.spec.js` | Automated |
| SPM-77 | Shortfall shows needing attention | TC-SPM77-AC04 | `e2e/spm77.spec.js` | Automated |
| SPM-77 | Accept shortfall or amend and resubmit | TC-SPM77-AC05 | `e2e/spm77.spec.js` | Automated |
| SPM-77 | Complete review marks arrangement ready | TC-SPM77-AC06 | `e2e/spm77.spec.js` | Automated |
| SPM-77 | Responses written to the activity log | TC-SPM77-AC07 | `e2e/spm77.spec.js` | Automated |
| SPM-78 | Reduce, increase, or release on an active event | TC-SPM78-AC01 | `e2e/spm78.spec.js` | Automated |
| SPM-78 | Increase uses the availability check | TC-SPM78-AC02 | `e2e/spm78.spec.js` | Automated |
| SPM-78 | Reduce or release returns units immediately | TC-SPM78-AC03 | `e2e/spm78.spec.js` | Automated |
| SPM-78 | Release on confirmed requires reason and notifies | TC-SPM78-AC04 | `e2e/spm78.spec.js` | Automated |
| SPM-78 | Release returns arrangement to needing attention | TC-SPM78-AC05 | `e2e/spm78.spec.js` | Automated |
| SPM-78 | Adjustments logged with old and new quantity | TC-SPM78-AC06 | `e2e/spm78.spec.js` | Automated |

A case is Pass only when every active test for that ID passes. A skipped
UI contract or assignment-gate check keeps the case Blocked even if the
active API test passed.
