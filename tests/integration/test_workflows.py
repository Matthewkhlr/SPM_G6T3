"""Run every service workflow through its HTTP API and its own SQL database.

Each service owns the ``app`` package, so the workflows run in separate
processes. Identity is supplied the same way the services read a bearer token;
the event, venue, equipment, registration, notification, and user records are
written and read through the real routers.
"""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = (
    "user-service",
    "event-service",
    "venue-service",
    "equipment-service",
    "registration-service",
    "notification-service",
)


class TestProjectWorkflows(unittest.TestCase):
    def test_every_service_workflow(self):
        for name in SERVICES:
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests/integration", "-p", "test_*.py", "-t", "."],
                cwd=ROOT / "services" / name,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"{name} failed\n{result.stdout}\n{result.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
