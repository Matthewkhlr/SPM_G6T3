# SPM-77 Respond to an equipment request that cannot be fully met

Official story has 7 acceptance criteria.

Automated tests (TC-SPM77-AC01–AC07)
Command: npm run test:spm77
Spec: e2e/spm77.spec.js
Setup: docs/testing/README.md
Test data: Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.

Item
Content
Test Case ID
TC-SPM77-AC01
Test Scenario
Verify Technical Support can mark a line unavailable with a reason, optional note, and suggested alternative.
Pre-conditions
A pending eq1 request exists on e3.
Test Steps
1. POST /unavailable with reason, note, and alternative eq2.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The line is unavailable and names eq2 as the alternative.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM77-AC02
Test Scenario
Verify Technical Support can record a line as partly fulfilled, reserving what is available and stating the shortfall.
Pre-conditions
A type has 2 units. The event asked for 4.
Test Steps
1. POST /partial with reservedQuantity 2.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
2 are reserved and the shortfall is 2.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM77-AC03
Test Scenario
Verify the assigned coordinator is notified with the line, the shortfall, the reason, and any suggested alternative.
Pre-conditions
TS-01 marked an e3 eq3 line unavailable, suggesting eq1.
Test Steps
1. Open e3 as EC-01.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The coordinator sees the line, the reason, and the alternative.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM77-AC04
Test Scenario
Verify a line marked unavailable or partly fulfilled shows the equipment arrangement as needing attention, not ready.
Pre-conditions
e3 already has eq-shortfall partly fulfilled.
Test Steps
1. GET /events/e3/readiness as EC-01.
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
TC-SPM77-AC05
Test Scenario
Verify the coordinator can accept the shortfall, which resolves the line, or amend the request and send it back.
Pre-conditions
Two shortfall lines exist on e3.
Test Steps
1. POST /accept-shortfall as EC-01 on the first.
2. PATCH quantity and resubmit on the second.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
Accepting resolves the line. Amending returns it to Requested.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.


Item
Content
Test Case ID
TC-SPM77-AC06
Test Scenario
Verify recording the whole request as reviewed and complete marks the equipment arrangement ready.
Pre-conditions
A new event has one equipment line.
Test Steps
1. POST /complete-review as TS-01.
2. GET readiness.
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


Item
Content
Test Case ID
TC-SPM77-AC07
Test Scenario
Verify every response is written to the activity log with who acted and when.
Pre-conditions
TS-01 has just marked a line unavailable.
Test Steps
1. GET the equipment activity log.
Test Data
Accounts TS-01, TS-02, EC-01, and EO-01 from Test Data/credentials-valid.txt. Equipment eq1–eq3 and requests eq-pending, eq-upcoming, eq-reverify, eq-shortfall from scripts/seed.py.
Expected Result
The log records the response for u4.
Actual Result
Not executed
Pass/Fail/Not Executed/Blocked
Not Executed
Remarks
Automated in Playwright.
