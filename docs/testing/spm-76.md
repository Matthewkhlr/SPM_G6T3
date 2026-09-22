# SPM-76 Record an event's equipment requirements

Official story has 4 acceptance criteria.

Automated tests (TC-SPM76-AC01–AC04)
Command: npm run test:spm76
Spec: e2e/spm76.spec.js
Setup: docs/testing/README.md
Test data: Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.

Item
Content
Test Case ID
TC-SPM76-AC01
Test Scenario
Verify a coordinator request captures equipment type, quantity, and technical requirements — not unit identifiers.
Pre-conditions
e3 is in planning and assigned to EC-01.
Test Steps
1. POST /equipment/requests as EC-01 for eq1 quantity 2 with an HDMI note.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The stored request has type, quantity, and the note, and no unit id.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM76-AC02
Test Scenario
Verify the request is visible to Technical Support as Requested, and only they can move it to Reserved or Unavailable.
Pre-conditions
EC-01 has just created a request on e3.
Test Steps
1. GET the request as TS-01.
2. POST reserve and unavailable as EC-01.
3. PATCH status reserved as EC-01.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Staff see Requested. Coordinator transitions are 403.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM76-AC03
Test Scenario
Verify once Technical Support acts, the record shows who last updated it and when.
Pre-conditions
A pending request exists on e3.
Test Steps
1. POST /review as TS-01.
2. Read reviewedBy and the timestamp.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The updater is u4 and a time is stored for the readiness view to read.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM76-AC04
Test Scenario
Verify a line that cannot be fulfilled is marked accordingly and the coordinator is notified.
Pre-conditions
EC-01 requested more eq3 than exists.
Test Steps
1. POST /unavailable as TS-01.
2. Open e3 as EC-01.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The request is unavailable and the coordinator can see the outcome.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.
