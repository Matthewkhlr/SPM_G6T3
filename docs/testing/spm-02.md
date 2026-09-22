# SPM-2 Check equipment availability

Official story has 9 acceptance criteria.

Automated tests (TC-SPM02-AC01–AC09)
Command: npm run test:spm02
Spec: e2e/spm02.spec.js
Setup: docs/testing/README.md
Test data: Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.

Item
Content
Test Case ID
TC-SPM02-AC01
Test Scenario
Verify the check reports each requested line with the quantity requested and the quantity available for the event's date and time.
Pre-conditions
TS-01 has created a type with 5 units. EC-01 has requested 2 of them on a planning event.
Test Steps
1. POST /equipment/availability for that event as TS-01.
2. Read the line for the created type.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The line shows requested 2 and available 5.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM02-AC02
Test Scenario
Verify the available quantity excludes units reserved for overlapping events.
Pre-conditions
A type has 4 units. Another event already holds 2 for an overlapping period.
Test Steps
1. Reserve 2 units for the holder event.
2. Check availability for a second overlapping event.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Available quantity is 2.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM02-AC03
Test Scenario
Verify the available quantity excludes damaged, under maintenance, or retired units.
Pre-conditions
A type has 6 units. One is damaged, one is under maintenance, one is retired.
Test Steps
1. PATCH the out-of-service counts.
2. Check availability for an event that requests the type.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Available quantity is 3.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM02-AC04
Test Scenario
Verify the check states whether the whole request can be met, and names each shortfall and by how much.
Pre-conditions
A type has 2 units. The event requests 4.
Test Steps
1. POST /equipment/availability as TS-01.
2. Read canMeet and the shortfall on the line.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The check says the request cannot be met and names a shortfall of 2.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM02-AC05
Test Scenario
Verify a shortfall names the overlapping events that hold the conflicting quantities.
Pre-conditions
A type has 3 units, all reserved to another overlapping event.
Test Steps
1. Reserve the holder event.
2. Check availability for the second event.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The shortfall lists the holder event so staff can negotiate.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM02-AC06
Test Scenario
Verify periods that merely touch do not compete for the same units.
Pre-conditions
Event A ends at the same instant event B begins. A holds every unit.
Test Steps
1. Reserve all units for A.
2. Check availability for B.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
B still sees the full stock.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM02-AC07
Test Scenario
Verify re-running the check after a reservation is made or released reflects the new position.
Pre-conditions
A type has 5 free units.
Test Steps
1. Check availability.
2. Reserve 2 on another overlapping event and check again.
3. Release that reservation and check again.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The figures move from 5 to 3 to 5.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM02-AC08
Test Scenario
Verify the check never itself reserves anything, and running it twice changes nothing.
Pre-conditions
An event has a request and no reservation yet.
Test Steps
1. POST /equipment/availability twice.
2. GET the type's reservations.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Both checks match, and no reservation was created.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM02-AC09
Test Scenario
Verify automated coverage of exact sufficiency, a shortfall of one, an overlapping reservation, out-of-service stock, and touching periods.
Pre-conditions
TS-01 can create isolated stock and events for each scenario.
Test Steps
1. Check a request whose quantity equals available stock.
2. Check a request for available plus one.
3. Reserve one overlapping unit and re-check.
4. Mark one unit damaged and re-check.
5. Reserve a touching period and re-check.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Exact fit can be met, shortfall is 1, overlap and out-of-service reduce stock, and touching periods do not.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.
