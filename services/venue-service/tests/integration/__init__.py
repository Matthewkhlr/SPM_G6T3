import os
import sys
import tempfile
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[2]
ROOT = SERVICE.parents[1]
sys.path[:0] = [str(SERVICE), str(ROOT)]
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.gettempdir()) / (SERVICE.name + '-integration.sqlite')}"
