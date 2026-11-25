"""Category management. Categories are a closed list, never free text."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..category_icons import CHOOSABLE_ICONS, DEFAULT_ICON
from ..db import get_db, utc_now
from ..schemas import (
    CategoryCreate,
    CategoryIconsOut,
    CategoryOrderIn,
    CategoryOut,
    CategoryUpdate,
)
from ..security import current_user

router = APIRouter(prefix="/categories", tags=["categories"], dependencies=[Depends(current_user)])

_SELECT = (
    "SELECT c.id, c.name, c.sort_order, c.is_active, c.system_key,"
    f" COALESCE(c.icon, '{DEFAULT_ICON}') AS icon,"
    " (SELECT COUNT(*) FROM expenses e WHERE e.category_id = c.id) AS expense_count"
    " FROM categories c"
)


def _clean(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise HTTPException(status_code=422, detail="Il nome non può essere vuoto.")
    return cleaned


def _check_icon(icon: str) -> str:
    if icon not in CHOOSABLE_ICONS:
        raise HTTPException(status_code=422, detail="Icona non disponibile: scegline una dall'elenco.")
    return icon


def _fetch(db: sqlite3.Connection, category_id: int) -> sqlite3.Row:
    row = db.execute(f"{_SELECT} WHERE c.id = ?", (category_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Categoria non trovata.")
    return row


def _protect_system(row: sqlite3.Row, action: str) -> None:
    """A category the app relies on (the Vinted section) stays available."""
    if row["system_key"] == "vinted":
        raise HTTPException(
            status_code=409,
            detail=f"La categoria {row['name']} serve alla sezione Vinted: non si può {action}.",
        )


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


@router.get("/icons", response_model=CategoryIconsOut)
def list_icons():
    """The icons an expense category can have, in the order of the picker."""
    return {"icons": list(CHOOSABLE_ICONS), "default": DEFAULT_ICON}


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryCreate, db: sqlite3.Connection = Depends(get_db)):
    name = _clean(body.name)
    icon = _check_icon(body.icon) if body.icon is not None else None
    _ensure_unique(db, name)
    next_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 10 FROM categories"
    ).fetchone()[0]
    cursor = db.execute(
        "INSERT INTO categories (name, name_key, sort_order, icon, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (name, name.casefold(), next_order, icon, utc_now()),
    )
    db.commit()
    return dict(_fetch(db, cursor.lastrowid))


@router.put("/order", response_model=list[CategoryOut])
def reorder_categories(body: CategoryOrderIn, db: sqlite3.Connection = Depends(get_db)):
    """Set the order of the categories in one go (0.14.0: the arrows in
    Impostazioni → Categorie). ``ids`` must list every category, active and
    not, each once; they get sort_order 10, 20, 30… in that order.

    One request instead of a PATCH per category: two people reordering at
    the same time cannot leave the list half done.
    """
    existing = {row["id"] for row in db.execute("SELECT id FROM categories")}
    if len(body.ids) != len(set(body.ids)) or set(body.ids) != existing:
        raise HTTPException(
            status_code=409,
            detail="L'elenco delle categorie è cambiato nel frattempo: ricarica e riprova.",
        )
    db.executemany(
        "UPDATE categories SET sort_order = ? WHERE id = ?",
        [((index + 1) * 10, category_id) for index, category_id in enumerate(body.ids)],
    )
    db.commit()
    return list_categories(include_inactive=True, db=db)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, body: CategoryUpdate, db: sqlite3.Connection = Depends(get_db)
):
    """Rename, reorder, deactivate or reactivate a category, or change its icon.

    Deactivating hides it from the entry screen; past expenses keep it.
    The Vinted category can be renamed, not deactivated.
    """
    current = _fetch(db, category_id)
    if body.is_active is False:
        _protect_system(current, "disattivare")
    if body.name is not None:
        name = _clean(body.name)
        _ensure_unique(db, name, exclude_id=category_id)
        db.execute(
            "UPDATE categories SET name = ?, name_key = ? WHERE id = ?",
            (name, name.casefold(), category_id),
        )
    if body.icon is not None:
        db.execute(
            "UPDATE categories SET icon = ? WHERE id = ?", (_check_icon(body.icon), category_id)
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
    _protect_system(row, "eliminare")
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
