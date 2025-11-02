"""Database session and base declarations."""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings

settings = get_settings()
url = make_url(settings.database_url)
connect_args: dict[str, object] = {}
if url.get_backend_name() == "sqlite":
    connect_args["check_same_thread"] = False
    if url.query.get("uri", "false").lower() == "true":
        connect_args["uri"] = True
engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
Base = declarative_base()

if url.get_backend_name() == "sqlite":
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover - engine configuration
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


@contextmanager
def session_scope() -> Iterator[sessionmaker]:
    """Provide a transactional scope for database interactions."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
