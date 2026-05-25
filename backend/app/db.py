import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


WORKSPACE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = WORKSPACE_DIR / "data" / "jlao-mvp.sqlite"


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def default_database_url() -> str:
    return f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"


def configure_database(database_url: str | None = None) -> Engine:
    global _engine, _SessionLocal

    url = database_url or os.getenv("DATABASE_URL") or default_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if url.startswith("sqlite:///"):
        db_file = Path(url.replace("sqlite:///", "", 1))
        if not db_file.is_absolute():
            db_file = WORKSPACE_DIR / db_file
        db_file.parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=MEMORY")
            cursor.execute("PRAGMA synchronous=OFF")
            cursor.close()

    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        return configure_database()
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        configure_database()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db() -> None:
    from app import db_models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
