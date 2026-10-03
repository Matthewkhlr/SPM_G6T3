#!/usr/bin/env python3
"""Run unittest + Coverage.py for every service and fail under 100%."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = [
    "user-service",
    "event-service",
    "venue-service",
    "equipment-service",
    "registration-service",
    "notification-service",
]


def main() -> int:
    failed = []
    for name in SERVICES:
        service = ROOT / "services" / name
        print(f"\n=== {name} ===", flush=True)
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "coverage",
                "run",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests/unit",
                "-p",
                "test_*.py",
                "-t",
                ".",
            ],
            cwd=service,
        )
        report = subprocess.run(
            [sys.executable, "-m", "coverage", "report", "--fail-under=100"],
            cwd=service,
        )
        html = subprocess.run([sys.executable, "-m", "coverage", "html"], cwd=service)
        if run.returncode or report.returncode or html.returncode:
            failed.append(name)
    if failed:
        print("Unit tests failed or coverage is below 100%:", ", ".join(failed))
        return 1
    print("\nAll six services are at 100% statement coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
