# Integration tests

Each service keeps one workflow test in `services/<service>/tests/integration/test_workflow.py`. The test calls that service through its HTTP API and reads the rows back from SQL. Auth and calls to other services stay stubbed, so a failure means this service's route, service code, and database disagree.

The suite uses a temporary SQLite file. Docker and MySQL stay stopped.

## Run

From the repository root:

```bash
npm run test:integration
```

`.github/workflows/tests.yml` runs the same command after the unit tests, on pushes to `dev` and `main` and on pull requests into either branch. The job id is `test`.

From one service directory:

```bash
cd services/event-service
python -m unittest discover -s tests/integration -p "test_*.py" -t .
```

Use `user-service`, `venue-service`, `equipment-service`, `registration-service`, or `notification-service` the same way.

## Files

| Service | What the workflow checks |
|---|---|
| user-service | An unknown token is refused. A linked account returns its role, and the directory lists that account. |
| event-service | A draft is saved with requirements, a full event is submitted, a readiness line is added, and the submitted event stays off the open-registration list. |
| venue-service | A venue is created and listed. An event with no booking returns an empty public summary. |
| equipment-service | A reservation above the stock is refused. A reservation, a shortfall, an adjustment, and a release are stored and appear on the activity log. |
| registration-service | The registration count for an event with no rows is zero, and the caller's list is empty. |
| notification-service | A notification record is stored and listed for the signed-in user. |

`tests/integration/test_workflows.py` runs those six files. It does not call the services over the network.
