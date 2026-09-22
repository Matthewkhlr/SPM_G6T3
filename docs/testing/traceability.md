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

A case is Pass only when every active test for that ID passes. A skipped
SPM-45 UI contract keeps the case Blocked even if the API test passed.
