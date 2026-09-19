#!/usr/bin/env python3
"""Apply Alembic migrations for every service, then seed demo data."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MYSQL_PORT = 3307

SERVICES = [
    ("user-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/user"),
    ("event-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/event"),
    ("venue-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/venue"),
    ("equipment-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/equipment"),
    ("registration-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/registration"),
    ("notification-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/notification"),
]


def wait_for_port(port: int, timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise SystemExit(f"Timed out waiting for MySQL on port {port}. Is Docker Compose up?")


def wait_for_mysql(url: str, timeout: int = 60) -> None:
    from sqlalchemy import create_engine, text

    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        engine = create_engine(url)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return
        except Exception as exc:  # noqa: BLE001 — retry until MySQL accepts connections
            last_error = exc
            engine.dispose()
            time.sleep(1)
    raise SystemExit(f"Timed out waiting for {url}: {last_error}")


def upgrade(service: str, url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    cwd = ROOT / "services" / service
    env["PYTHONPATH"] = str(cwd)
    print(f"alembic upgrade head  ({service})")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=cwd,
        env=env,
        check=True,
    )


def _require_deps() -> None:
    try:
        import alembic  # noqa: F401
        import pymysql  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            f"Missing dependency ({exc}). Activate the project venv, then run:\n"
            "  pip install -r services/user-service/requirements.txt"
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate ConnectSphere MySQL databases.")
    parser.add_argument("--no-seed", action="store_true", help="Skip demo data inserts.")
    args = parser.parse_args()
    _require_deps()

    print(f"waiting for shared MySQL on :{MYSQL_PORT}")
    wait_for_port(MYSQL_PORT)

    for service, url in SERVICES:
        print(f"checking {service} schema")
        wait_for_mysql(url)
        upgrade(service, url)

    if not args.no_seed:
        from seed import seed_all

        seed_all()
        print("seed complete")
    print("migrate complete")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
