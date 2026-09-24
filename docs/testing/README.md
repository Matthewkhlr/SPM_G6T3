# Acceptance Testing

Playwright covers SPM-43, the current SPM-45 API, the current SPM-46 API,
the SPM-47 tenant-isolation contract, the role-home contracts for
SPM-55 through SPM-59, the venue-catalogue contracts for SPM-8, SPM-9,
SPM-10, SPM-17, and SPM-60 through SPM-64 and SPM-108, and the
planning-review contracts for SPM-5, SPM-15, and SPM-65 through SPM-73,
and the equipment contracts for SPM-2, SPM-3, SPM-4, and SPM-75 through
SPM-78, and the request-and-change contracts for SPM-14, SPM-79 through
SPM-83, SPM-85 through SPM-88, and SPM-106, and the
registration-and-notification contracts for SPM-11, SPM-12, SPM-89
through SPM-95, SPM-105, and SPM-6, and the Firebase auth contract for
SPM-51. Case tables live in the team
test-case document. This folder is the run guide.

## Prerequisites

- Docker Desktop
- Python deps for the services
- `npm install` at the repo root and in `frontend/`
- `npx playwright install chromium`
- Repo-root `.env` from `.env.example` (Firebase web + Admin credentials)
- Seeded accounts from `Test Data/credentials-valid.txt`

## Run

From the repository root:

```bash
npm run test:acceptance
```

This starts MySQL, migrates, seeds, starts the backends and Vue app, then runs
the suite.

```bash
npm run test:spm43
npm run test:spm45
npm run test:spm46
npm run test:spm47
npm run test:spm55
npm run test:spm56
npm run test:spm57
npm run test:spm58
npm run test:spm59
npm run test:spm08
npm run test:spm09
npm run test:spm10
npm run test:spm17
npm run test:spm60
npm run test:spm61
npm run test:spm62
npm run test:spm63
npm run test:spm64
npm run test:spm108
npm run test:spm05
npm run test:spm15
npm run test:spm65
npm run test:spm66
npm run test:spm68
npm run test:spm69
npm run test:spm70
npm run test:spm71
npm run test:spm72
npm run test:spm73
npm run test:spm02
npm run test:spm03
npm run test:spm04
npm run test:spm75
npm run test:spm76
npm run test:spm77
npm run test:spm78
npm run test:spm14
npm run test:spm79
npm run test:spm80
npm run test:spm81
npm run test:spm82
npm run test:spm83
npm run test:spm85
npm run test:spm86
npm run test:spm87
npm run test:spm88
npm run test:spm106
npm run test:spm11
npm run test:spm12
npm run test:spm89
npm run test:spm90
npm run test:spm91
npm run test:spm92
npm run test:spm105
npm run test:spm06
npm run test:spm93
npm run test:spm94
npm run test:spm95
npm run test:spm51
```

`test:acceptance` omits SPM-47, SPM-55 through SPM-59, the venue epic
above, the planning-review epic (SPM-5, SPM-15, SPM-65 through SPM-73),
the equipment epic (SPM-2, SPM-3, SPM-4, SPM-75 through SPM-78), the
request-and-change epic (SPM-14, SPM-79 through SPM-83, SPM-85 through
SPM-88, and SPM-106), and the registration-and-notification epic
(SPM-11, SPM-12, SPM-89 through SPM-95, SPM-105, and SPM-6), and
SPM-51. Use the story commands as their contracts.

Failures: `test-results/`. HTML report: `playwright-report/`.

## Specs

| Story | Cases | Spec |
|---|---|---|
| SPM-43 | TC-SPM43-AC01–AC07 | `e2e/spm43.spec.js` |
| SPM-45 API | TC-SPM45-AC01–AC04 | `e2e/spm45-api.spec.js` |
| SPM-45 UI | TC-SPM45-AC01–AC04 | `e2e/spm45-ui.contract.spec.js` (skipped until those screens exist) |
| SPM-46 API | TC-SPM46-AC01–AC03 | `e2e/spm46-api.spec.js` |
| SPM-46 UI | TC-SPM46-AC01–AC03 | `e2e/spm46-ui.contract.spec.js` (skipped until event details exists) |
| SPM-47 API | TC-SPM47-AC01–AC03 | `e2e/spm47-api.spec.js` (fails until tenant isolation ships) |
| SPM-47 UI | TC-SPM47-AC01–AC03 | `e2e/spm47-ui.contract.spec.js` (skipped until those screens exist) |
| SPM-55 | TC-SPM55-AC01–AC07 | `e2e/spm55.spec.js` |
| SPM-56 | TC-SPM56-AC01–AC07 | `e2e/spm56.spec.js` |
| SPM-57 | TC-SPM57-AC01–AC06 | `e2e/spm57.spec.js` |
| SPM-58 | TC-SPM58-AC01–AC07 | `e2e/spm58.spec.js` |
| SPM-59 | TC-SPM59-AC01–AC06 | `e2e/spm59.spec.js` |
| SPM-8 | TC-SPM08-AC01–AC09 | `e2e/spm08.spec.js` |
| SPM-9 | TC-SPM09-AC01–AC08 | `e2e/spm09.spec.js` |
| SPM-10 | TC-SPM10-AC01–AC07 | `e2e/spm10.spec.js` |
| SPM-17 | TC-SPM17-AC01–AC06 | `e2e/spm17.spec.js` |
| SPM-60 | TC-SPM60-AC01–AC09 | `e2e/spm60.spec.js` |
| SPM-61 | TC-SPM61-AC01–AC08 | `e2e/spm61.spec.js` |
| SPM-62 | TC-SPM62-AC01–AC09 | `e2e/spm62.spec.js` |
| SPM-63 | TC-SPM63-AC01–AC09 | `e2e/spm63.spec.js` |
| SPM-64 | TC-SPM64-AC01–AC07 | `e2e/spm64.spec.js` |
| SPM-108 | TC-SPM108-AC01–AC08 | `e2e/spm108.spec.js` |
| SPM-5 | TC-SPM05-AC01–AC09 | `e2e/spm05.spec.js` |
| SPM-15 | TC-SPM15-AC01–AC09 | `e2e/spm15.spec.js` |
| SPM-65 | TC-SPM65-AC01–AC07 | `e2e/spm65.spec.js` |
| SPM-66 | TC-SPM66-AC01–AC08 | `e2e/spm66.spec.js` |
| SPM-68 | TC-SPM68-AC01–AC08 | `e2e/spm68.spec.js` |
| SPM-69 | TC-SPM69-AC01–AC06 | `e2e/spm69.spec.js` |
| SPM-70 | TC-SPM70-AC01–AC07 | `e2e/spm70.spec.js` |
| SPM-71 | TC-SPM71-AC01–AC07 | `e2e/spm71.spec.js` |
| SPM-72 | TC-SPM72-AC01–AC06 | `e2e/spm72.spec.js` |
| SPM-73 | TC-SPM73-AC01–AC06 | `e2e/spm73.spec.js` |
| SPM-2 | TC-SPM02-AC01–AC09 | `e2e/spm02.spec.js` |
| SPM-3 | TC-SPM03-AC01–AC10 | `e2e/spm03.spec.js` |
| SPM-4 | TC-SPM04-AC01–AC07 | `e2e/spm04.spec.js` |
| SPM-75 | TC-SPM75-AC01–AC07 | `e2e/spm75.spec.js` |
| SPM-76 | TC-SPM76-AC01–AC04 | `e2e/spm76.spec.js` |
| SPM-77 | TC-SPM77-AC01–AC07 | `e2e/spm77.spec.js` |
| SPM-78 | TC-SPM78-AC01–AC06 | `e2e/spm78.spec.js` |
| SPM-14 | TC-SPM14-AC01–AC07 | `e2e/spm14.spec.js` |
| SPM-79 | TC-SPM79-AC01–AC06 | `e2e/spm79.spec.js` |
| SPM-80 | TC-SPM80-AC01–AC07 | `e2e/spm80.spec.js` |
| SPM-81 | TC-SPM81-AC01–AC07 | `e2e/spm81.spec.js` |
| SPM-82 | TC-SPM82-AC01–AC07 | `e2e/spm82.spec.js` |
| SPM-83 | TC-SPM83-AC01–AC05 | `e2e/spm83.spec.js` |
| SPM-85 | TC-SPM85-AC01–AC09 | `e2e/spm85.spec.js` |
| SPM-86 | TC-SPM86-AC01–AC10 | `e2e/spm86.spec.js` |
| SPM-87 | TC-SPM87-AC01–AC09 | `e2e/spm87.spec.js` |
| SPM-88 | TC-SPM88-AC01–AC11 | `e2e/spm88.spec.js` |
| SPM-106 | TC-SPM106-AC01–AC10 | `e2e/spm106.spec.js` |
| SPM-11 | TC-SPM11-AC01–AC10 | `e2e/spm11.spec.js` |
| SPM-12 | TC-SPM12-AC01–AC09 | `e2e/spm12.spec.js` |
| SPM-89 | TC-SPM89-AC01–AC07 | `e2e/spm89.spec.js` |
| SPM-90 | TC-SPM90-AC01–AC07 | `e2e/spm90.spec.js` |
| SPM-91 | TC-SPM91-AC01–AC09 | `e2e/spm91.spec.js` |
| SPM-92 | TC-SPM92-AC01–AC08 | `e2e/spm92.spec.js` |
| SPM-105 | TC-SPM105-AC01–AC06 | `e2e/spm105.spec.js` |
| SPM-6 | TC-SPM06-AC01–AC04 | `e2e/spm06.spec.js` |
| SPM-93 | TC-SPM93-AC01–AC11 | `e2e/spm93.spec.js` |
| SPM-94 | TC-SPM94-AC01–AC08 | `e2e/spm94.spec.js` |
| SPM-95 | TC-SPM95-AC01–AC08 | `e2e/spm95.spec.js` |
| SPM-51 | TC-SPM51-AC01–AC04 | `e2e/spm51.spec.js` |

SPM-43 uses `Test Data/credentials-valid.txt` and `credentials-invalid.txt`.
SPM-45 through SPM-95 and SPM-51 use valid credentials only. Invalid login is 401;
wrong role or cross-tenant access is 403 or 404.

When a skipped UI screen ships, remove the matching `test.skip` and re-run the
story command. Assignment-gated 403s stay skipped until venue/equipment APIs
check assignment, not only role.

See [traceability.md](traceability.md).
