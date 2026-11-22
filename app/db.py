"""SQLite access: connections, migrations and small shared helpers.

Plain sqlite3 from the standard library, no ORM: the schema is a handful of
tables.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings
from .text import fold

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# Tables of schema version 1: any backup of this app has them. Tables added
# later (recurring_expenses, incomes, recurring_incomes, vinted_items,
# vinted_photos) are created by migrate() after a restore.
REQUIRED_TABLES = {"users", "sessions", "categories", "merchants", "expenses"}


def utc_now() -> str:
    """Current time as an ISO 8601 UTC string, second precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: Path) -> sqlite3.Connection:
    # check_same_thread=False: FastAPI may create and use the per-request
    # connection on different worker threads (never concurrently).
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # fold(): text without case and accents, for the search (0.9.0).
    conn.create_function("fold", 1, fold, deterministic=True)
    return conn


def list_migrations() -> list[tuple[int, Path]]:
    migrations = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        migrations.append((int(path.name.split("_", 1)[0]), path))
    return migrations


def latest_schema_version() -> int:
    migrations = list_migrations()
    return migrations[-1][0] if migrations else 0


def migrate(conn: sqlite3.Connection) -> None:
    """Apply pending migrations. Idempotent and safe to run on every start."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, path in list_migrations():
        if version <= current:
            continue
        sql = path.read_text(encoding="utf-8")
        # One transaction per migration: schema change and version bump
        # either both land or neither does.
        try:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


def init_db() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(settings.db_path)
    try:
        migrate(conn)
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request.

    Endpoints that write call ``db.commit()`` themselves before returning, so
    the data is durable before the client can send its next request. The
    commit below is only a safety net.
    """
    conn = connect(get_settings().db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
