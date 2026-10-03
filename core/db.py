"""Database engine, session factory and initialisation."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, MetaData, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from core.models import SCHEMA_VERSION, Base


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_sqlite_fks(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _schema_version(bind: Engine) -> int:
    with bind.connect() as conn:
        return conn.execute(text("PRAGMA user_version")).scalar() or 0


def _set_schema_version(bind: Engine) -> None:
    with bind.begin() as conn:
        conn.execute(text(f"PRAGMA user_version = {SCHEMA_VERSION}"))


def _drop_everything(bind: Engine) -> None:
    """Drop every table, including ones from older schema versions that the models no longer know."""
    meta = MetaData()
    meta.reflect(bind)
    with bind.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        meta.drop_all(conn)
        conn.execute(text("PRAGMA foreign_keys=ON"))


def init_db(bind: Engine = engine) -> bool:
    """Create tables. A demo DB from an older schema version is rebuilt (returns True if so).

    Hackathon-only: there are no migrations, and the data is synthetic and re-seedable.
    """
    rebuilt = False
    if bind.dialect.name == "sqlite" and inspect(bind).get_table_names() and _schema_version(bind) != SCHEMA_VERSION:
        _drop_everything(bind)
        rebuilt = True
    Base.metadata.create_all(bind)
    if bind.dialect.name == "sqlite":
        _set_schema_version(bind)
    return rebuilt


def reset_db(bind: Engine = engine) -> None:
    _drop_everything(bind)
    Base.metadata.create_all(bind)
    if bind.dialect.name == "sqlite":
        _set_schema_version(bind)


@contextmanager
def get_session() -> Iterator[Session]:
    """Commit on success, roll back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
