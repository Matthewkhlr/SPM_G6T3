# Acceptance Testing

Playwright covers SPM-43 and the current SPM-45 API. Case tables live in the
team test-case document. This folder is the run guide.

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
```

Failures: `test-results/`. HTML report: `playwright-report/`.

## Specs

| Story | Cases | Spec |
|---|---|---|
| SPM-43 | TC-SPM43-AC01–AC07 | `e2e/spm43.spec.js` |
| SPM-45 API | TC-SPM45-AC01–AC04 | `e2e/spm45-api.spec.js` |
| SPM-45 UI | TC-SPM45-AC01–AC04 | `e2e/spm45-ui.contract.spec.js` (skipped until those screens exist) |

SPM-43 uses `Test Data/credentials-valid.txt` and `credentials-invalid.txt`.
SPM-45 uses valid credentials only. Invalid login is 401; wrong role is 403.

When a skipped SPM-45 UI screen ships, remove the matching `test.skip` and run
`npm run test:spm45`.

See [traceability.md](traceability.md).
