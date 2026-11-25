"""Checks shared by the routers that write expenses, incomes, recurring
templates and Vinted items. Each one raises the HTTP error the app shows
(422 with an Italian message) instead of returning a flag.

Until 0.13.0 these lived in routers/expenses.py as private helpers and the
other routers imported them from there.
"""

from __future__ import annotations

import sqlite3

from fastapi import HTTPException

from .money import AmountError, parse_amount


def require_amount(text: str) -> int:
    """The typed amount in cents ("12,50" -> 1250), or 422 with the reason."""
    try:
        return parse_amount(text)
    except AmountError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def check_category(db: sqlite3.Connection, category_id: int, must_be_active: bool) -> None:
    """The expense category exists (and is active, when asked)."""
    row = db.execute(
        "SELECT is_active FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail="Categoria non valida.")
    if must_be_active and not row["is_active"]:
        raise HTTPException(status_code=422, detail="Questa categoria è disattivata.")


def check_user(db: sqlite3.Connection, user_id: int) -> None:
    """The user exists (who paid, who received)."""
    if db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
        raise HTTPException(status_code=422, detail="Utente non valido.")


def clean_note(note: str | None) -> str | None:
    """A note without surrounding spaces; an empty one is no note."""
    if note is None:
        return None
    return note.strip() or None
