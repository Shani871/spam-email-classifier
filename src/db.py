"""Database schema, engine and migrations.

The database is chosen by SPAMGUARD_DATABASE_URL (or DATABASE_URL, or POSTGRES_HOST with
POSTGRES_USER, POSTGRES_DB and POSTGRES_PASSWORD_FILE as set by Docker Compose):
  - PostgreSQL in production, e.g. postgresql+psycopg://user:password@db:5432/spamguard
  - SQLite for local development and tests (default: data/spamguard.db)

The schema is created and upgraded by Alembic migrations in migrations/, applied
automatically the first time a process uses the database. On PostgreSQL an advisory
lock makes concurrent start-ups wait for each other instead of racing.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import threading

from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, Index, Integer, MetaData, String, Table, Text,
                        create_engine, event, text)
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = ROOT / "data" / "spamguard.db"
MIGRATIONS_DIR = ROOT / "migrations"
MIGRATION_LOCK_ID = 74_211_908  # arbitrary constant for pg_advisory_lock

metadata = MetaData()

history = Table(
    "history", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("assessment", String(40), nullable=False),
    Column("score", Integer, nullable=True),
    Column("category", String(40), nullable=False),
    Index("ix_history_account_created", "account_id", "created_at"),
    Index("ix_history_expires_at", "expires_at"),
)

feedback = Table(
    "feedback", metadata,
    Column("id", String(64), primary_key=True),
    Column("account_id", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("text", Text, nullable=False),
    Column("predicted_label", String(16), nullable=False, server_default=""),
    Column("user_label", String(8), nullable=False),
    Column("user_comment", Text, nullable=False, server_default=""),
    Column("consent_given", Boolean, nullable=False, server_default=text("false")),
    Column("status", String(16), nullable=False, server_default="pending"),
    Column("rejection_reason", Text, nullable=False, server_default=""),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("user_label IN ('ham', 'spam')", name="ck_feedback_user_label"),
    CheckConstraint("status IN ('pending', 'approved', 'rejected', 'withdrawn')", name="ck_feedback_status"),
    Index("ix_feedback_account_created", "account_id", "created_at"),
    Index("ix_feedback_review", "consent_given", "status", "expires_at"),
)

sender_rules = Table(
    "sender_rules", metadata,
    Column("account_id", String(64), primary_key=True),
    Column("address", String(320), primary_key=True),
    Column("rule", String(8), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("rule IN ('trust', 'block')", name="ck_sender_rules_rule"),
)

deleted_accounts = Table(
    "deleted_accounts", metadata,
    Column("account_id", String(64), primary_key=True),
    Column("deleted_at", DateTime(timezone=True), nullable=False),
)

ACCOUNT_TABLES = (history, feedback, sender_rules)

_engines = {}
_migrated = set()
_lock = threading.Lock()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value):
    """SQLite returns naive datetimes; treat them as UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _postgres_url_from_parts() -> str:
    """Build a PostgreSQL URL from POSTGRES_HOST and friends, reading the password from a file.

    Used by Docker Compose, which passes the password as a secret file
    (POSTGRES_PASSWORD_FILE) instead of an environment variable or a URL.
    """
    from urllib.parse import quote
    host = os.environ.get("POSTGRES_HOST", "").strip()
    if not host:
        return ""
    password = os.environ.get("POSTGRES_PASSWORD", "")
    password_file = os.environ.get("POSTGRES_PASSWORD_FILE", "")
    if password_file:
        password = Path(password_file).read_text(encoding="utf-8").strip()
    user = os.environ.get("POSTGRES_USER", "spamguard")
    name = os.environ.get("POSTGRES_DB", "spamguard")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{quote(name, safe='')}"


def database_url() -> str:
    url = os.environ.get("SPAMGUARD_DATABASE_URL") or os.environ.get("DATABASE_URL") or _postgres_url_from_parts()
    if url.startswith("postgres://"):  # common shorthand from hosting providers
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url or f"sqlite:///{DEFAULT_SQLITE_PATH}"


def is_sqlite(url: str = "") -> bool:
    return (url or database_url()).startswith("sqlite")


def _new_engine(url: str) -> Engine:
    if is_sqlite(url):
        path = url.split("///", 1)[-1]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, future=True)

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, future=True)


def get_engine() -> Engine:
    """Engine for the configured database, with migrations applied (once per process)."""
    url = database_url()
    with _lock:
        engine = _engines.get(url)
        if engine is None:
            engine = _engines[url] = _new_engine(url)
        if url not in _migrated:
            migrate(engine)
            _migrated.add(url)
    return engine


def migrate(engine: Engine) -> None:
    """Apply Alembic migrations up to the latest version."""
    from alembic import command
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", str(engine.url).replace("%", "%%"))
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID})
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def reset_engines() -> None:
    """Forget cached engines (tests, or after restoring a SQLite backup)."""
    with _lock:
        for engine in _engines.values():
            engine.dispose()
        _engines.clear()
        _migrated.clear()


def health_check() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
