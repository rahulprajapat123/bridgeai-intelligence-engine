from __future__ import annotations

from collections.abc import Generator
import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from research_intel.config import Settings, get_settings
from research_intel.models import Base


def build_engine(settings: Settings | None = None):
    settings = settings or get_settings()
    connect_args = {}
    if settings.sqlalchemy_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif settings.sqlalchemy_url.startswith("postgresql"):
        connect_args["connect_timeout"] = 30  # Increased for Neon
        connect_args["keepalives"] = 1
        connect_args["keepalives_idle"] = 30
        connect_args["keepalives_interval"] = 10
        connect_args["keepalives_count"] = 5
    return create_engine(
        settings.sqlalchemy_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_size=5,  # Reduced for Neon free tier limits
        max_overflow=2,  # Allow 2 extra connections during spikes
        pool_timeout=30,  # Wait up to 30s for a connection
        pool_use_lifo=True,
        echo=False,
    )


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


SCHEMA_PATCHES: dict[str, dict[str, str]] = {
    "research_items": {
        "publisher": "TEXT DEFAULT ''",
        "credibility_breakdown": "JSON DEFAULT '{}'::json" ,
        "cleaned_text": "TEXT DEFAULT ''",
        "parse_status": "VARCHAR(32) DEFAULT 'parsed'",
    },
    "claims": {
        "domain_tags": "JSON DEFAULT '[]'::json",
        "citation_url": "TEXT DEFAULT ''",
        "source_quote": "TEXT DEFAULT ''",
    },
    "query_logs": {
        "brief_id": "VARCHAR(64)",
        "query_text": "TEXT DEFAULT ''",
    },
    "daily_intelligence_reports": {
        "topics": "JSON DEFAULT '[]'::json",
        "recipients": "JSON DEFAULT '[]'::json",
    },
}


def _column_spec(dialect_name: str, spec: str) -> str:
    if dialect_name != "postgresql":
        return spec.replace("::json", "")
    return spec


def ensure_schema_compatibility(bind_engine=None) -> None:
    active_engine = bind_engine or engine
    inspector = inspect(active_engine)
    dialect_name = active_engine.dialect.name
    with active_engine.begin() as conn:
        for table_name, columns in SCHEMA_PATCHES.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, spec in columns.items():
                if column_name in existing_columns:
                    continue
                conn.execute(
                    text(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} "
                        f"{_column_spec(dialect_name, spec)}"
                    )
                )


def init_db(bind_engine=None) -> None:
    active_engine = bind_engine or engine
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            Base.metadata.create_all(active_engine)
            ensure_schema_compatibility(active_engine)
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(1 + attempt)
    if last_error:
        raise last_error


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
