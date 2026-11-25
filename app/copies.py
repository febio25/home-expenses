"""Copies of the database kept on the server (0.14.0).

Three kinds, all in the folder ``snapshots`` inside the data folder, so
umbrelOS Backups (when turned on) carry them off the Umbrel too:

- ``daily-YYYY-MM-DD.db``: one a day, the last DAILY_KEEP days;
- ``pre-update-vN-YYYYMMDD-HHMMSS.db``: the database as it was before an
  update changed its schema (N = schema version before), the last 3;
- ``pre-restore-YYYYMMDD-HHMMSS.db``: the data a restore replaced, the
  last 3 (until 0.13.0 they sat in the data folder itself).

They protect from mistakes (a wrong restore, a deletion, an update gone
bad), not from a broken disk: that is what the downloaded backup and
umbrelOS Backups are for. Every copy is made with SQLite's online backup
API, so it is consistent even while the app is writing.

Also here: who downloaded the last backup, and when (a small JSON file in
the data folder, outside the database: a restore must not bring back an
old date).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import dates
from .config import Settings, get_settings

logger = logging.getLogger(__name__)

COPIES_DIRNAME = "snapshots"
LAST_DOWNLOAD_FILENAME = "last-backup-download.json"
DAILY_KEEP = 7
PRE_UPDATE_KEEP = 3
PRE_RESTORE_KEEP = 3
# How often the running app checks whether today's copy exists.
DAILY_CHECK_SECONDS = 3600

KIND_PREFIXES = {"daily": "daily-", "pre_update": "pre-update-", "pre_restore": "pre-restore-"}
# The only names accepted back from a client: no folders, no other files.
COPY_NAME = re.compile(r"^(daily|pre-update|pre-restore)-[0-9A-Za-z-]+\.db$")


def copies_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.data_dir / COPIES_DIRNAME


def _new_path(folder: Path, prefix: str) -> Path:
    """``<prefix><UTC time>.db``, with a counter when a copy of the same
    second exists: a copy must never overwrite another one (restoring a
    pre-restore copy makes a new pre-restore copy at once)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = folder / f"{prefix}{stamp}.db"
    counter = 1
    while path.exists() or path.with_name(path.name + ".part").exists():
        counter += 1
        path = folder / f"{prefix}{stamp}-{counter}.db"
    return path


def snapshot(source_path: Path, target_path: Path) -> None:
    """Consistent copy of a live database, via SQLite's online backup API.
    Written to a temporary name first: a half-written file is never listed."""
    from .db import connect  # db imports this module

    target_path.parent.mkdir(parents=True, exist_ok=True)
    partial = target_path.with_name(target_path.name + ".part")
    source = connect(source_path)
    target = sqlite3.connect(partial)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    partial.replace(target_path)


def _by_age(paths) -> list[Path]:
    """Oldest first: by modification time, then by name. Not by name alone:
    two copies of the same second are told apart by a counter ("-2"),
    which would sort before the first one."""
    return sorted(paths, key=lambda path: (path.stat().st_mtime_ns, path.name))


def prune(kind: str, keep: int, settings: Settings | None = None) -> None:
    """Keep the ``keep`` newest copies of a kind."""
    folder = copies_dir(settings)
    copies = _by_age(folder.glob(f"{KIND_PREFIXES[kind]}*.db"))
    for old in copies[:-keep] if keep else copies:
        old.unlink(missing_ok=True)


def move_legacy_pre_restore(settings: Settings) -> None:
    """Copies made by a restore before 0.14.0 sat in the data folder: move
    them in with the others, so they are listed and kept in check."""
    folder = copies_dir(settings)
    for path in sorted(settings.data_dir.glob("pre-restore-*.db")):
        folder.mkdir(parents=True, exist_ok=True)
        path.replace(folder / path.name)


def pre_update_copy(settings: Settings, schema_version: int) -> None:
    """The database before migrations change it. Called by init_db only
    when there is something to migrate and data to protect."""
    snapshot(settings.db_path, _new_path(copies_dir(settings), f"pre-update-v{schema_version}-"))
    prune("pre_update", PRE_UPDATE_KEEP, settings)


def pre_restore_copy(settings: Settings) -> None:
    """The data about to be replaced by a restore. Pruned only after the
    restore (see backup.py), so restoring the oldest copy never deletes it
    before it is read."""
    snapshot(settings.db_path, _new_path(copies_dir(settings), "pre-restore-"))


def ensure_daily_copy(settings: Settings | None = None) -> Path | None:
    """Today's copy, made if missing; the oldest ones beyond DAILY_KEEP go.
    Nothing before the first-run setup: an empty database is not worth it."""
    settings = settings or get_settings()
    if not settings.db_path.exists():
        return None
    target = copies_dir(settings) / f"daily-{dates.today().isoformat()}.db"
    if target.exists():
        return None
    conn = sqlite3.connect(settings.db_path)
    try:
        has_users = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone() and conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    finally:
        conn.close()
    if not has_users:
        return None
    snapshot(settings.db_path, target)
    prune("daily", DAILY_KEEP, settings)
    logger.info("Daily copy written: %s", target.name)
    return target


def list_copies(settings: Settings | None = None) -> list[dict]:
    """Every copy, newest first."""
    folder = copies_dir(settings)
    if not folder.is_dir():
        return []
    copies = []
    for path in reversed(_by_age(folder.glob("*.db"))):
        if not COPY_NAME.match(path.name):
            continue
        kind = next(kind for kind, prefix in KIND_PREFIXES.items() if path.name.startswith(prefix))
        stat = path.stat()
        copies.append({
            "name": path.name,
            "kind": kind,
            "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "size_bytes": stat.st_size,
        })
    return copies


def copy_path(name: str, settings: Settings | None = None) -> Path | None:
    """The file of a listed copy, or None for any other name."""
    if not COPY_NAME.match(name):
        return None
    path = copies_dir(settings) / name
    return path if path.is_file() else None


def record_download(user_name: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    data = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user_name": user_name,
    }
    path = settings.data_dir / LAST_DOWNLOAD_FILENAME
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(data), encoding="utf-8")
    partial.replace(path)


def last_download(settings: Settings | None = None) -> dict | None:
    settings = settings or get_settings()
    try:
        data = json.loads((settings.data_dir / LAST_DOWNLOAD_FILENAME).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None
    if not isinstance(data, dict) or not {"at", "user_name"} <= data.keys():
        return None
    return {"at": str(data["at"]), "user_name": str(data["user_name"])}
