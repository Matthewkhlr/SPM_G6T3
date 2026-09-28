import os
import sys
import tempfile
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[2]
ROOT = SERVICE.parents[1]
sys.path[:0] = [str(SERVICE), str(ROOT)]

_db = Path(tempfile.gettempdir()) / f"{SERVICE.name}-unit.sqlite"
try:
    _db.unlink()
except FileNotFoundError:
    pass
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
