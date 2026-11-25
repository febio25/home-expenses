"""Full database backup download and restore from file; from 0.14.0 also
the copies kept on the server (app/copies.py) and the date of the last
download."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from .. import copies
from ..config import MAX_RESTORE_BYTES, get_settings
from ..db import REQUIRED_TABLES, connect, latest_schema_version, migrate
from ..schemas import BackupsOut, MessageOut
from ..security import current_user

router = APIRouter(tags=["backup"], dependencies=[Depends(current_user)])

SQLITE_MAGIC = b"SQLite format 3\x00"


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


@router.get("/backup", response_class=FileResponse)
def download_backup(user: sqlite3.Row = Depends(current_user)):
    """Download the complete database as a single SQLite file.

    The file contains everything, password hashes included: keep it private.
    The download is recorded (0.14.0): GET /backups says when and by whom.
    """
    settings = get_settings()
    handle, temp_path = tempfile.mkstemp(prefix="backup-", suffix=".db", dir=settings.data_dir)
    os.close(handle)
    try:
        copies.snapshot(settings.db_path, Path(temp_path))
    except Exception:
        _remove(temp_path)
        raise
    copies.record_download(user["display_name"])
    # UTC, marked as such: the container has no time zone. The app names
    # the file with the phone's own time instead.
    filename = f"spese-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}Z.db"
    return FileResponse(
        temp_path,
        media_type="application/octet-stream",
        filename=filename,
        headers={"Cache-Control": "no-store"},
        background=BackgroundTask(_remove, temp_path),
    )


def _validate_upload(path: Path) -> None:
    """Refuse anything that is not a healthy backup of this app."""
    with open(path, "rb") as file:
        if file.read(len(SQLITE_MAGIC)) != SQLITE_MAGIC:
            raise HTTPException(
                status_code=422, detail="Il file non è un backup valido di Spese di Casa."
            )
    conn = sqlite3.connect(path)
    try:
        check = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] if "users" in tables else 0
    except sqlite3.DatabaseError as error:
        raise HTTPException(
            status_code=422, detail="Il file è danneggiato e non può essere ripristinato."
        ) from error
    finally:
        conn.close()
    if check != "ok":
        raise HTTPException(
            status_code=422, detail="Il file è danneggiato e non può essere ripristinato."
        )
    if not REQUIRED_TABLES.issubset(tables):
        raise HTTPException(
            status_code=422, detail="Il file non è un backup valido di Spese di Casa."
        )
    if version > latest_schema_version():
        raise HTTPException(
            status_code=422,
            detail="Il backup viene da una versione più recente dell'app: aggiorna l'app e riprova.",
        )
    if users == 0:
        raise HTTPException(
            status_code=422, detail="Il backup non contiene utenti: non può essere ripristinato."
        )


def _restore(upload_path: Path) -> None:
    settings = get_settings()
    _validate_upload(upload_path)

    # Keep a copy of what is about to be replaced.
    copies.pre_restore_copy(settings)

    # Overwrite the live database in place through the backup API: SQLite
    # handles the locking, no file is swapped under open connections.
    source = sqlite3.connect(upload_path)
    live = connect(settings.db_path)
    try:
        source.backup(live)
        migrate(live)  # bring an older backup up to the current schema
    finally:
        live.close()
        source.close()
    # Only now: the copy being restored may itself be the oldest one.
    copies.prune("pre_restore", copies.PRE_RESTORE_KEEP, settings)


@router.post("/restore", response_model=MessageOut)
async def restore_backup(request: Request):
    """Replace all data with the content of a backup file.

    Send the file as the raw request body (``application/octet-stream``).
    Sessions come from the backup too, so signing in again may be needed.
    """
    settings = get_settings()
    handle, temp_path = tempfile.mkstemp(prefix="restore-", suffix=".db", dir=settings.data_dir)
    size = 0
    try:
        with os.fdopen(handle, "wb") as file:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_RESTORE_BYTES:
                    raise HTTPException(status_code=413, detail="File troppo grande.")
                file.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="Nessun file ricevuto.")
        await run_in_threadpool(_restore, Path(temp_path))
    finally:
        _remove(temp_path)
    return {"detail": "Ripristino completato."}


@router.get("/backups", response_model=BackupsOut)
def list_backups():
    """The copies kept on the server, newest first, and the last download
    of a backup (0.14.0)."""
    return {"last_download": copies.last_download(), "copies": copies.list_copies()}


@router.post("/backups/{name}/restore", response_model=MessageOut)
def restore_copy(name: str):
    """Replace all data with one of the copies kept on the server, with the
    same checks as a restore from file. The data replaced becomes a
    ``pre-restore`` copy, so this can be undone the same way."""
    path = copies.copy_path(name)
    if path is None:
        raise HTTPException(status_code=404, detail="Copia non trovata.")
    _restore(path)
    return {"detail": "Ripristino completato."}
