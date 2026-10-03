import os
import tempfile
from pathlib import Path

# Point the app-level engine at a throwaway DB before core.db is imported,
# so UI smoke tests never touch the developer's demo database.
_TEST_DB = Path(tempfile.gettempdir()) / "healthbridge_test.db"
_TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ["UPLOAD_DIR"] = str(Path(tempfile.gettempdir()) / "healthbridge_test_uploads")
os.environ["AI_ENABLED"] = "false"

import pytest  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from core.db import init_db, make_engine  # noqa: E402


@pytest.fixture
def engine():
    eng = make_engine("sqlite:///:memory:")
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine) -> Session:
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture
def seeded(session) -> Session:
    from data.seed import seed

    seed(session)
    session.commit()
    return session


@pytest.fixture
def actor(seeded):
    """actor("Dr. Ayesha Malik", "City Hospital") -> Actor in that organization context (primary org by default)."""
    from sqlalchemy import select

    from core.models import Organization, User
    from services import user_service

    def make(name: str, org_name: str | None = None):
        user = seeded.scalar(select(User).where(User.name == name))
        org_id = seeded.scalar(select(Organization.id).where(Organization.name == org_name)) if org_name else None
        return user_service.make_actor(seeded, user.id, org_id)

    return make


@pytest.fixture
def pid(seeded):
    """pid("Ahmed Khan") -> patient id."""
    from sqlalchemy import select

    from core.models import Patient

    return lambda name: seeded.scalar(select(Patient.id).where(Patient.name == name))
