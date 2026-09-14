import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHONPATH = str(ROOT)

SERVICES = [
    ("user-service", 8001),
    ("event-service", 8002),
    ("venue-service", 8003),
    ("equipment-service", 8004),
    ("registration-service", 8005),
    ("notification-service", 8006),
]


def main():
    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHONPATH
    procs = []
    for name, port in SERVICES:
        cwd = ROOT / "services" / name
        print(f"starting {name} on {port}")
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", str(port)],
                cwd=cwd,
                env=env,
            )
        )
    try:
        for proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        for proc in procs:
            proc.terminate()


if __name__ == "__main__":
    main()
