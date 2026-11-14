"""Category management. Categories are a closed list, never free text."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db, utc_now
from ..schemas import CategoryCreate, CategoryOut, CategoryUpdate
from ..security import current_user

router = APIRouter(prefix="/categories", tags=["categories"], dependencies=[Depends(current_user)])

_SELECT = (
    "SELECT c.id, c.name, c.sort_order, c.is_active,"
    " (SELECT COUNT(*) FROM expenses e WHERE e.category_id = c.id) AS expense_count"
    " FROM categories c"
)


def _clean(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise HTTPException(status_code=422, detail="Il nome non può essere vuoto.")
    return cleaned


def _fetch(db: sqlite3.Connection, category_id: int) -> sqlite3.Row:
    row = db.execute(f"{_SELECT} WHERE c.id = ?", (category_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Categoria non trovata.")
    return row


def _ensure_unique(db: sqlite3.Connection, name: str, exclude_id: int | None = None) -> None:
    row = db.execute(
        "SELECT id FROM categories WHERE name_key = ?", (name.casefold(),)
    ).fetchone()
    if row is not None and row["id"] != exclude_id:
        raise HTTPException(status_code=409, detail="Esiste già una categoria con questo nome.")


@router.get("", response_model=list[CategoryOut])
def list_categories(include_inactive: bool = False, db: sqlite3.Connection = Depends(get_db)):
    where = "" if include_inactive else " WHERE c.is_active = 1"
    rows = db.execute(f"{_SELECT}{where} ORDER BY c.sort_order, c.id").fetchall()
    return [dict(row) for row in rows]


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryCreate, db: sqlite3.Connection = Depends(get_db)):
    name = _clean(body.name)
    _ensure_unique(db, name)
    next_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 10 FROM categories"
    ).fetchone()[0]
    cursor = db.execute(
        "INSERT INTO categories (name, name_key, sort_order, created_at) VALUES (?, ?, ?, ?)",
        (name, name.casefold(), next_order, utc_now()),
    )
    db.commit()
    return dict(_fetch(db, cursor.lastrowid))


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, body: CategoryUpdate, db: sqlite3.Connection = Depends(get_db)
):
    """Rename, reorder, deactivate or reactivate a category.

    Deactivating hides it from the entry screen; past expenses keep it.
    """
    _fetch(db, category_id)
    if body.name is not None:
        name = _clean(body.name)
        _ensure_unique(db, name, exclude_id=category_id)
        db.execute(
            "UPDATE categories SET name = ?, name_key = ? WHERE id = ?",
            (name, name.casefold(), category_id),
        )
    if body.is_active is not None:
        if not body.is_active:
            active = db.execute(
                "SELECT COUNT(*) FROM categories WHERE is_active = 1 AND id != ?",
                (category_id,),
            ).fetchone()[0]
            if active == 0:
                raise HTTPException(
                    status_code=409, detail="Deve restare almeno una categoria attiva."
                )
        db.execute(
            "UPDATE categories SET is_active = ? WHERE id = ?",
            (int(body.is_active), category_id),
        )
    if body.sort_order is not None:
        db.execute(
            "UPDATE categories SET sort_order = ? WHERE id = ?", (body.sort_order, category_id)
        )
    db.commit()
    return dict(_fetch(db, category_id))


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Delete a category that has never been used. Used ones can only be deactivated."""
    row = _fetch(db, category_id)
    if row["expense_count"] > 0:
        raise HTTPException(
            status_code=409,
            detail="Questa categoria ha spese collegate: puoi solo disattivarla.",
        )
    if db.execute(
        "SELECT 1 FROM recurring_expenses WHERE category_id = ? LIMIT 1", (category_id,)
    ).fetchone():
        raise HTTPException(
            status_code=409,
            detail="Questa categoria è usata da una spesa ricorrente: puoi solo disattivarla.",
        )
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
