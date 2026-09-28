"""SQLite session reset shared by the unittest suites.

Each test rebinds the service engine to the sqlite file chosen in
``tests/unit/__init__.py``, so TestClient and the test session share one
database and nothing reaches MySQL.
"""

import os
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        import app.db.session as session_module
        import app.main  # noqa: F401 — imports routers, config, and the app object
        import app.models  # noqa: F401 — registers every model on Base.metadata

        engine = create_engine(
            os.environ["DATABASE_URL"],
            connect_args={"check_same_thread": False},
        )
        session_module.engine = engine
        session_module.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        self.engine = engine
        self.Base = session_module.Base
        self.SessionLocal = session_module.SessionLocal
        self.Base.metadata.drop_all(self.engine)
        self.Base.metadata.create_all(self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def close_db_dependency(self):
        from app.db import session as session_module

        if hasattr(session_module, "init_db"):
            self.assertIsNone(session_module.init_db())
        generator = session_module.get_db()
        session = next(generator)
        self.assertIsNotNone(session)
        generator.close()
