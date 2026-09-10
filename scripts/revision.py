#!/usr/bin/env python3
"""Generate an Alembic revision for one service (works on Windows and Unix)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from migrate import SERVICES

SERVICE_URLS = {name: url for name, url, _port in SERVICES}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an Alembic revision for a service.")
    parser.add_argument("service", choices=sorted(SERVICE_URLS), help="Service folder name under services/")
    parser.add_argument("-m", "--message", required=True, help="Revision message")
    args = parser.parse_args()

    cwd = ROOT / "services" / args.service
    env = os.environ.copy()
    env["DATABASE_URL"] = SERVICE_URLS[args.service]
    env["PYTHONPATH"] = str(cwd)
    print(f"alembic revision --autogenerate -m {args.message!r}  ({args.service})")
    subprocess.run(
        [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", args.message],
        cwd=cwd,
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
