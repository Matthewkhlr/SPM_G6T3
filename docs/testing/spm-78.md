# SPM-78 Adjust or release an equipment reservation

Official story has 6 acceptance criteria.

Automated tests (TC-SPM78-AC01–AC06)
Command: npm run test:spm78
Spec: e2e/spm78.spec.js
Setup: docs/testing/README.md
Test data: Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.

Item
Content
Test Case ID
TC-SPM78-AC01
Test Scenario
Verify Technical Support can reduce, increase, or release a reservation on an event that is not Completed, Cancelled, or Rejected.
Pre-conditions
A reservation of 2 exists on a planning event. A second reservation sits on an event that is then rejected.
Test Steps
1. PATCH quantity to 3, then 1.
2. POST /release.
3. PATCH the rejected event's reservation.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Active events can be adjusted. Terminal events cannot.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM78-AC02
Test Scenario
Verify increasing a reservation is subject to the same availability check as making one.
Pre-conditions
A type has 2 units and 1 is already reserved.
Test Steps
1. PATCH the reservation to quantity 5.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The increase is refused and available stock is stated.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM78-AC03
Test Scenario
Verify reducing or releasing a reservation immediately returns the units to availability for the period.
Pre-conditions
3 of 4 units are reserved. Another event is watching the same period.
Test Steps
1. Reduce to 1 and re-check.
2. Release and re-check.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Availability moves from 1 to 3 to 4.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM78-AC04
Test Scenario
Verify releasing a reservation on a confirmed event requires a reason and notifies the assigned coordinator and the Event Organiser.
Pre-conditions
e1 is confirmed. TS-01 has reserved a created type on e1.
Test Steps
1. POST /release with no reason. Confirm 400 or 422.
2. POST /release with a reason.
3. Open e1 as EC-01 and as EO-01.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
A reason is mandatory. Both the coordinator and the organiser can see the release.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM78-AC05
Test Scenario
Verify releasing a reservation shows the event's equipment arrangement as needing attention again.
Pre-conditions
A new event was fully reserved.
Test Steps
1. POST /release.
2. GET readiness.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The equipment arrangement needs attention.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM78-AC06
Test Scenario
Verify every adjustment and release is written to the activity log with previous quantity, new quantity, actor, and time.
Pre-conditions
TS-01 reduced a reservation from 2 to 1.
Test Steps
1. GET the equipment activity log.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The log has previous 2, new 1, and u4.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.
