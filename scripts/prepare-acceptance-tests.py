#!/usr/bin/env python3
"""Prepare the local stack used by Playwright acceptance tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ENV = (
    "VITE_FIREBASE_API_KEY",
    "VITE_FIREBASE_AUTH_DOMAIN",
    "VITE_FIREBASE_PROJECT_ID",
    "VITE_FIREBASE_APP_ID",
)


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        raise SystemExit("Missing .env. Copy .env.example and add test Firebase credentials.")

    # python-dotenv is already part of the backend dependencies.
    from dotenv import load_dotenv

    load_dotenv(env_file)


def _require_environment() -> None:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if not (os.getenv("FIREBASE_CREDENTIALS_JSON") or os.getenv("FIREBASE_CREDENTIALS_PATH")):
        missing.append("FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH")
    if missing:
        raise SystemExit(f"Missing acceptance-test environment values: {', '.join(missing)}")


def main() -> None:
    _load_dotenv()
    _require_environment()

    print("starting acceptance-test MySQL")
    subprocess.run(
        ["docker", "compose", "-f", str(ROOT / "infra" / "docker-compose.yml"), "up", "-d"],
        cwd=ROOT,
        check=True,
    )

    print("applying migrations and ensuring demo accounts exist")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "migrate.py")], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
