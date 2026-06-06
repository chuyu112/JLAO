import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


WORKSPACE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = WORKSPACE_DIR / "data" / "jlao-mvp.sqlite"


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def default_database_url() -> str:
    return f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"


def _normalize_database_url(url: str) -> str:
    cleaned = url.strip()
    if cleaned.startswith("postgres://"):
        return f"postgresql+psycopg://{cleaned.removeprefix('postgres://')}"
    if cleaned.startswith("postgresql://"):
        return f"postgresql+psycopg://{cleaned.removeprefix('postgresql://')}"
    return cleaned


def configure_database(database_url: str | None = None) -> Engine:
    global _engine, _SessionLocal

    url = _normalize_database_url(database_url or os.getenv("DATABASE_URL") or default_database_url())
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine_kwargs = {"poolclass": StaticPool} if url == "sqlite:///:memory:" else {}
    if url.startswith("sqlite:///"):
        db_file = Path(url.replace("sqlite:///", "", 1))
        if not db_file.is_absolute():
            db_file = WORKSPACE_DIR / db_file
        db_file.parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(url, connect_args=connect_args, future=True, **engine_kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
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

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations(engine)


def _run_lightweight_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "products" not in table_names:
        return

    with engine.begin() as connection:
        product_columns = _table_columns(connection, "products")
        if "status" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN status VARCHAR(50)"))
            connection.execute(text("UPDATE products SET status = '在售' WHERE status IS NULL OR status = ''"))

        if "style" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN style VARCHAR(100)"))
            connection.execute(text("UPDATE products SET style = '' WHERE style IS NULL"))
        if "theme" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN theme VARCHAR(100)"))
            connection.execute(text("UPDATE products SET theme = '' WHERE theme IS NULL"))
        if "evidence_image_paths" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN evidence_image_paths JSON"))
            connection.execute(text("UPDATE products SET evidence_image_paths = '[]' WHERE evidence_image_paths IS NULL"))
        if "evidence_texts" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN evidence_texts JSON"))
            connection.execute(text("UPDATE products SET evidence_texts = '[]' WHERE evidence_texts IS NULL"))
        if "analysis_confidence" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN analysis_confidence FLOAT"))
            connection.execute(text("UPDATE products SET analysis_confidence = 0 WHERE analysis_confidence IS NULL"))
        if "attribute_sources" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN attribute_sources JSON"))
            connection.execute(text("UPDATE products SET attribute_sources = '{}' WHERE attribute_sources IS NULL"))
        if "fusion_scores" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN fusion_scores JSON"))
            connection.execute(text("UPDATE products SET fusion_scores = '{}' WHERE fusion_scores IS NULL"))
        if "live_sessions" in table_names:
            session_columns = _table_columns(connection, "live_sessions")
            if "live_room_name" not in session_columns:
                connection.execute(text("ALTER TABLE live_sessions ADD COLUMN live_room_name VARCHAR(255)"))
                connection.execute(text("UPDATE live_sessions SET live_room_name = '' WHERE live_room_name IS NULL"))

        if "virtual_customer_events" in table_names:
            event_columns = _table_columns(connection, "virtual_customer_events")
            if "repeat_count" not in event_columns:
                connection.execute(text("ALTER TABLE virtual_customer_events ADD COLUMN repeat_count INTEGER"))
                connection.execute(text("UPDATE virtual_customer_events SET repeat_count = 1 WHERE repeat_count IS NULL"))
            if "last_seen_at" not in event_columns:
                connection.execute(text("ALTER TABLE virtual_customer_events ADD COLUMN last_seen_at DATETIME"))

        if "frame_snapshots" in table_names:
            frame_columns = _table_columns(connection, "frame_snapshots")
            frame_migrations = {
                "jade_color": ("VARCHAR(100)", "''"),
                "jade_water": ("VARCHAR(100)", "''"),
                "jade_style": ("VARCHAR(100)", "''"),
                "jade_theme": ("VARCHAR(100)", "''"),
                "jade_size": ("VARCHAR(255)", "''"),
                "jade_price": ("FLOAT", None),
                "jade_confidence": ("FLOAT", "0"),
                "jade_attribute_sources": ("JSON", "'{}'"),
                "jade_color_analysis": ("JSON", "'{}'"),
                "jade_detections": ("JSON", "'[]'"),
                "jade_ocr_text": ("TEXT", "''"),
                "jade_ocr_lines": ("JSON", "'[]'"),
                "jade_ocr_error": ("TEXT", "''"),
            }
            for column_name, (column_type, default_sql) in frame_migrations.items():
                if column_name not in frame_columns:
                    connection.execute(text(f"ALTER TABLE frame_snapshots ADD COLUMN {column_name} {column_type}"))
                    if default_sql is not None:
                        connection.execute(
                            text(f"UPDATE frame_snapshots SET {column_name} = {default_sql} WHERE {column_name} IS NULL")
                        )


def _table_columns(connection, table_name: str) -> set[str]:
    if connection.dialect.name != "sqlite":
        return {column["name"] for column in inspect(connection).get_columns(table_name)}
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    if rows:
        return {str(row[1]) for row in rows}
    return set()


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
