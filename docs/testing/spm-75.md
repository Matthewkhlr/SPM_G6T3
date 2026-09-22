# SPM-75 Equipment catalogue with quantities and operational status

Official story has 7 acceptance criteria.

Automated tests (TC-SPM75-AC01–AC07)
Command: npm run test:spm75
Spec: e2e/spm75.spec.js
Setup: docs/testing/README.md
Test data: Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.

Item
Content
Test Case ID
TC-SPM75-AC01
Test Scenario
Verify an equipment record holds a code, name, category, description, total quantity owned, home location, and optional technical notes.
Pre-conditions
TS-01 can create catalogue records.
Test Steps
1. POST a new type.
2. GET it back.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Every published field is stored.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM75-AC02
Test Scenario
Verify each record carries unavailable counts for damaged, under maintenance, or retired, subtracted from the total rather than deleted.
Pre-conditions
A type owns 6 units.
Test Steps
1. PATCH out-of-service to damaged 1, maintenance 2, retired 1.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Total stays 6 and serviceable quantity is 2.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM75-AC03
Test Scenario
Verify the quantity available to reserve is total owned, minus out of service, minus overlapping reservations.
Pre-conditions
A type owns 8 units, 2 out of service, 2 reserved for an overlapping event.
Test Steps
1. POST /equipment/availability for that period.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Available quantity is 4.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM75-AC04
Test Scenario
Verify Technical Support Staff can add and edit records; other roles have read-only access, enforced on the server.
Pre-conditions
eq1 exists.
Test Steps
1. GET eq1 as EC-01. Confirm 200.
2. POST and PATCH as EC-01, VS-01, and ATT-01. Confirm 403.
3. POST a type as TS-01. Confirm 201.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Writes are technical-support only.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM75-AC05
Test Scenario
Verify an out-of-service count raised above the total owned is rejected.
Pre-conditions
A type owns 3 units.
Test Steps
1. PATCH damaged 2 and maintenance 2.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The change is rejected.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM75-AC06
Test Scenario
Verify raising out-of-service below already reserved stock lists the events, requires acknowledgement, and notifies coordinators.
Pre-conditions
3 of 4 units are reserved for a future event.
Test Steps
1. PATCH damaged 2 without acknowledgement. Confirm 409 and the event is named.
2. PATCH again with acknowledgement.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The first save is blocked; the second succeeds.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM75-AC07
Test Scenario
Verify every change to quantities or out-of-service counts is written to the activity log.
Pre-conditions
TS-01 has just changed total quantity and a damaged count.
Test Steps
1. GET /equipment/{id}/activity-log.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The log records the quantity and out-of-service edits.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.
