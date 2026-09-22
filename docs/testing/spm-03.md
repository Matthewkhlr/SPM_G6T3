# SPM-3 Reserve equipment for an event

Official story has 10 acceptance criteria.

Automated tests (TC-SPM03-AC01–AC10)
Command: npm run test:spm03
Spec: e2e/spm03.spec.js
Setup: docs/testing/README.md
Test data: Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.

Item
Content
Test Case ID
TC-SPM03-AC01
Test Scenario
Verify Technical Support Staff can reserve a quantity up to what is available for the event's period.
Pre-conditions
A type has 4 free units. The event requests 3.
Test Steps
1. POST /equipment/reservations for quantity 3 as TS-01.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The reservation is created for 3 units on that event.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM03-AC02
Test Scenario
Verify a quantity above what is available is refused, the available quantity is stated, and nothing is reserved.
Pre-conditions
A type has 2 free units. The attempt is for 5.
Test Steps
1. POST /equipment/reservations for quantity 5.
2. GET the type's reservations.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The call is refused, available 2 is stated, and no row is stored.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM03-AC03
Test Scenario
Verify a reservation reduces the quantity available to any other overlapping event.
Pre-conditions
A type has 5 units.
Test Steps
1. Reserve 2 for event A.
2. Check availability for overlapping event B.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
B sees 3 available.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM03-AC04
Test Scenario
Verify units recorded as damaged, under maintenance, or retired can never be reserved.
Pre-conditions
A type has 3 units, all out of service.
Test Steps
1. PATCH out-of-service counts to 3.
2. POST a reservation for 1.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The reservation is refused.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM03-AC05
Test Scenario
Verify when two reservations for the last available unit are submitted together, exactly one succeeds.
Pre-conditions
A type has 1 unit. Two events request it for the same period.
Test Steps
1. POST both reservations at the same time.
2. Read both responses.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
One is 201 and the other is refused with the shortfall explained.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM03-AC06
Test Scenario
Verify a reservation stays associated with its event and is visible on the event and the equipment record.
Pre-conditions
TS-01 has reserved a created type for a planning event.
Test Steps
1. Open the event.
2. Open the equipment record.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Both screens show the same quantity, event, and period.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM03-AC07
Test Scenario
Verify the assigned coordinator can see the reservations and is notified when the request is fully reserved.
Pre-conditions
EC-01 is assigned. TS-01 reserves the full requested quantity.
Test Steps
1. Sign in as EC-01 and open the event.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The coordinator sees the reservation as fully reserved.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM03-AC08
Test Scenario
Verify cancelling, rejecting, or completing the event releases its reservations.
Pre-conditions
A reservation exists on a newly assigned event.
Test Steps
1. Reject the event as EC-01.
2. GET the reservation.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The reservation is released and the units are free again.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM03-AC09
Test Scenario
Verify reservations and releases persist in the activity log with who acted and when.
Pre-conditions
TS-01 reserved and then released a type.
Test Steps
1. GET /equipment/{id}/activity-log as TS-01.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The log has a reserve row and a release row for u4.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM03-AC10
Test Scenario
Verify reserving the full requested quantity for every line marks the equipment arrangement ready.
Pre-conditions
The event has one equipment line for 2 units.
Test Steps
1. Reserve 2.
2. GET the event readiness as EC-01.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The equipment arrangement is ready.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.
