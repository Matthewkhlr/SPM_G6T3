# SPM-4 View upcoming events

Official story has 7 acceptance criteria.

Automated tests (TC-SPM04-AC01–AC07)
Command: npm run test:spm04
Spec: e2e/spm04.spec.js
Setup: docs/testing/README.md
Test data: Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.

Item
Content
Test Case ID
TC-SPM04-AC01
Test Scenario
Verify the queue lists upcoming events that have equipment requirements, soonest first.
Pre-conditions
e1 and e2 have equipment lines. e1 is sooner.
Test Steps
1. GET /equipment/queue as TS-01.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
e1 and e2 are listed, e1 before e2.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM04-AC02
Test Scenario
Verify each row shows name, date, start and end time, status, venue if booked, coordinator, and equipment summary.
Pre-conditions
e1 is AI in Events Summit, assigned to Ben Lee.
Test Steps
1. Sign in as TS-01 and open Upcoming Events.
2. Read the e1 row.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The row carries every required field.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM04-AC03
Test Scenario
Verify each row shows whether the request is awaiting review, partly reserved, fully reserved, or unavailable.
Pre-conditions
e1 has a pending line and a reserved line. e3 has a partial LED-wall line.
Test Steps
1. Open Upcoming Events as TS-01.
2. Read data-equipment-state on e1 and e3.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The four request states are represented in plain language.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM04-AC04
Test Scenario
Verify requests needing attention, including re-verification, are shown first within the same date.
Pre-conditions
e2 is flagged for re-verification.
Test Steps
1. GET /equipment/queue.
2. Group rows by date and check order.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Attention rows come first on their date. e2 is marked for re-verification.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM04-AC05
Test Scenario
Verify the queue can be filtered by status and date range, and completed and cancelled events are excluded by default.
Pre-conditions
e8 is cancelled.
Test Steps
1. GET /equipment/queue.
2. Open Upcoming Events and confirm e8 is absent.
3. Set a status and date-range filter.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Cancelled e8 is not in the default queue.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM04-AC06
Test Scenario
Verify events with no equipment requirements do not appear.
Pre-conditions
e6 has empty equipment requirements.
Test Steps
1. GET /equipment/queue as TS-01.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
e6 is absent.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM04-AC07
Test Scenario
Verify Technical Support Staff can open an event from the queue to check availability and reserve.
Pre-conditions
e1 is on the queue.
Test Steps
1. Open Upcoming Events as TS-01.
2. Open the e1 row.
3. Confirm the check and reserve controls.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The event opens onto availability and reserve.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.
