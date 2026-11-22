"""Merchants: autocomplete source, rename and merge."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db, utc_now
from ..schemas import MerchantMerge, MerchantOut, MerchantUpdate
from ..security import current_user

router = APIRouter(prefix="/merchants", tags=["merchants"], dependencies=[Depends(current_user)])

# last_category_id: category of the most recently entered expense, offered as
# the default the next time this merchant is picked. Inactive categories are
# not suggested, nor the Vinted one (0.8.0): after buying an item to resell
# on Vinted, a purchase for the house from the same merchant must start
# without it.
_SELECT = """
SELECT m.id, m.name,
       (SELECT COUNT(*) FROM expenses e WHERE e.merchant_id = m.id) AS expense_count,
       (SELECT e.category_id FROM expenses e
          JOIN categories c ON c.id = e.category_id AND c.is_active = 1 AND c.system_key IS NULL
         WHERE e.merchant_id = m.id
         ORDER BY e.created_at DESC, e.id DESC LIMIT 1) AS last_category_id
  FROM merchants m
"""


def clean_merchant_name(name: str | None) -> str | None:
    """Trim and collapse whitespace. Returns None for an empty name."""
    if name is None:
        return None
    cleaned = " ".join(name.split())
    return cleaned or None


def merchant_key(name: str) -> str:
    return name.casefold()


def get_or_create_merchant(db: sqlite3.Connection, name: str | None) -> int | None:
    """Resolve a typed merchant name to an id, ignoring case and extra spaces."""
    cleaned = clean_merchant_name(name)
    if cleaned is None:
        return None
    row = db.execute(
        "SELECT id FROM merchants WHERE name_key = ?", (merchant_key(cleaned),)
    ).fetchone()
    if row is not None:
        return row["id"]
    cursor = db.execute(
        "INSERT INTO merchants (name, name_key, created_at) VALUES (?, ?, ?)",
        (cleaned, merchant_key(cleaned), utc_now()),
    )
    return cursor.lastrowid


def prune_merchant(db: sqlite3.Connection, merchant_id: int | None) -> None:
    """Drop a merchant no expense refers to anymore, so typos do not linger
    in the autocomplete after being corrected."""
    if merchant_id is None:
        return
    db.execute(
        "DELETE FROM merchants WHERE id = ?"
        " AND NOT EXISTS (SELECT 1 FROM expenses WHERE merchant_id = ?)",
        (merchant_id, merchant_id),
    )


def _rename_in_templates(db: sqlite3.Connection, old_name: str, new_name: str) -> None:
    """Recurring templates store the merchant as text: follow renames and merges."""
    old_key = merchant_key(old_name)
    rows = db.execute(
        "SELECT id, merchant_name FROM recurring_expenses WHERE merchant_name IS NOT NULL"
    ).fetchall()
    for row in rows:
        if merchant_key(row["merchant_name"]) == old_key:
            db.execute(
                "UPDATE recurring_expenses SET merchant_name = ? WHERE id = ?", (new_name, row["id"])
            )


def _fetch(db: sqlite3.Connection, merchant_id: int) -> sqlite3.Row:
    row = db.execute(f"{_SELECT} WHERE m.id = ?", (merchant_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Esercente non trovato.")
    return row


@router.get("", response_model=list[MerchantOut])
def list_merchants(db: sqlite3.Connection = Depends(get_db)):
    """All merchants, most used first. The client filters as the user types."""
    rows = db.execute(f"{_SELECT} ORDER BY expense_count DESC, m.name_key").fetchall()
    return [dict(row) for row in rows]


@router.patch("/{merchant_id}", response_model=MerchantOut)
def rename_merchant(
    merchant_id: int, body: MerchantUpdate, db: sqlite3.Connection = Depends(get_db)
):
    old = _fetch(db, merchant_id)
    name = clean_merchant_name(body.name)
    if name is None:
        raise HTTPException(status_code=422, detail="Il nome non può essere vuoto.")
    other = db.execute(
        "SELECT id FROM merchants WHERE name_key = ? AND id != ?",
        (merchant_key(name), merchant_id),
    ).fetchone()
    if other is not None:
        raise HTTPException(
            status_code=409,
            detail="Esiste già un esercente con questo nome: usa «Unisci» per fonderli.",
        )
    db.execute(
        "UPDATE merchants SET name = ?, name_key = ? WHERE id = ?",
        (name, merchant_key(name), merchant_id),
    )
    _rename_in_templates(db, old["name"], name)
    db.commit()
    return dict(_fetch(db, merchant_id))


@router.post("/{merchant_id}/merge", response_model=MerchantOut)
def merge_merchant(
    merchant_id: int, body: MerchantMerge, db: sqlite3.Connection = Depends(get_db)
):
    """Move every expense of this merchant to ``into_id`` and delete this one."""
    if body.into_id == merchant_id:
        raise HTTPException(status_code=422, detail="Scegli un esercente diverso.")
    source = _fetch(db, merchant_id)
    target = _fetch(db, body.into_id)
    db.execute(
        "UPDATE expenses SET merchant_id = ?, updated_at = ? WHERE merchant_id = ?",
        (body.into_id, utc_now(), merchant_id),
    )
    db.execute("DELETE FROM merchants WHERE id = ?", (merchant_id,))
    _rename_in_templates(db, source["name"], target["name"])
    db.commit()
    return dict(_fetch(db, body.into_id))
