"""Incomes: create, list, edit, delete.

Kept apart from expenses on purpose: separate table, endpoints and CSV, so
nothing changes for the expense entry screen, its totals and its export.
Categories are a fixed list (``INCOME_CATEGORIES`` in schemas.py).
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..dates import check_expense_date, range_filter, resolve_range
from ..db import get_db, utc_now
from ..schemas import INCOME_CATEGORIES, IncomeCategoryOut, IncomeCreate, IncomeOut, IncomeUpdate
from ..security import current_user
from .expenses import _amount, _check_user, _clean_note

router = APIRouter(prefix="/incomes", tags=["incomes"])

INCOME_SELECT = """
SELECT i.id, i.amount_cents, i.income_date, i.category, i.note,
       i.received_by_user_id, receiver.display_name AS received_by_name,
       i.created_by_user_id, author.display_name AS created_by_name,
       i.created_at, i.updated_at,
       v.id AS vinted_item_id, v.title AS vinted_item_title
  FROM incomes i
  JOIN users receiver ON receiver.id = i.received_by_user_id
  JOIN users author ON author.id = i.created_by_user_id
  LEFT JOIN vinted_items v ON v.sale_income_id = i.id
"""


def income_out(row: sqlite3.Row) -> dict:
    data = dict(row)
    # A code dropped from the list in a later version still shows, as itself.
    data["category_name"] = INCOME_CATEGORIES.get(data["category"], data["category"])
    return data


def fetch_income(db: sqlite3.Connection, income_id: int) -> dict:
    row = db.execute(f"{INCOME_SELECT} WHERE i.id = ?", (income_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Entrata non trovata.")
    return income_out(row)


def _by_client_uuid(db: sqlite3.Connection, client_uuid: str | None) -> int | None:
    if not client_uuid:
        return None
    row = db.execute("SELECT id FROM incomes WHERE client_uuid = ?", (client_uuid,)).fetchone()
    return row["id"] if row else None


# Declared before /{income_id}, so "categories" is never read as an id.
@router.get("/categories", response_model=list[IncomeCategoryOut])
def list_income_categories(user: sqlite3.Row = Depends(current_user)):
    """The fixed list of income categories, in display order."""
    return [{"code": code, "name": name} for code, name in INCOME_CATEGORIES.items()]


@router.get("", response_model=list[IncomeOut])
def list_incomes(
    month: str | None = Query(None, description="YYYY-MM; wins over from/to"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Incomes in the range, newest first. Without parameters: all of them."""
    start, end = resolve_range(month, date_from, date_to)
    where, params = range_filter(start, end, column="i.income_date")
    rows = db.execute(
        f"{INCOME_SELECT}{where} ORDER BY i.income_date DESC, i.id DESC", params
    ).fetchall()
    return [income_out(row) for row in rows]


def insert_income(
    db: sqlite3.Connection, user: sqlite3.Row, body: IncomeCreate
) -> tuple[int, bool]:
    """Insert an income without committing. Returns (id, created).

    With a ``client_uuid`` already known, nothing is inserted and the id of
    the existing income is returned with ``created`` False. Also used when
    registering a recurring income, inside the same transaction.
    """
    existing = _by_client_uuid(db, body.client_uuid)
    if existing is not None:
        return existing, False

    amount_cents = _amount(body.amount)
    check_expense_date(body.income_date)  # same window as expenses: 2000 to today
    received_by = body.received_by_user_id if body.received_by_user_id is not None else user["id"]
    _check_user(db, received_by)

    now = utc_now()
    try:
        cursor = db.execute(
            "INSERT INTO incomes (client_uuid, amount_cents, income_date, category, note,"
            " received_by_user_id, created_by_user_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                body.client_uuid,
                amount_cents,
                body.income_date.isoformat(),
                body.category,
                _clean_note(body.note),
                received_by,
                user["id"],
                now,
                now,
            ),
        )
    except sqlite3.IntegrityError:
        # Two identical retries raced: the other one won, return its row.
        db.rollback()
        existing = _by_client_uuid(db, body.client_uuid)
        if existing is None:
            raise
        return existing, False
    return cursor.lastrowid, True


@router.post("", response_model=IncomeOut, status_code=201)
def create_income(
    body: IncomeCreate,
    response: Response,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Record an income.

    Retrying with the same ``client_uuid`` (for example after a dropped
    connection) returns the income already saved, with status 200.
    """
    income_id, created = insert_income(db, user, body)
    if created:
        db.commit()
    else:
        response.status_code = 200
    return fetch_income(db, income_id)


@router.get("/{income_id}", response_model=IncomeOut)
def get_income(
    income_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return fetch_income(db, income_id)


@router.patch("/{income_id}", response_model=IncomeOut)
def update_income(
    income_id: int,
    body: IncomeUpdate,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Change only the fields present in the body. ``"note": null`` clears the note."""
    current = fetch_income(db, income_id)
    sent = body.model_fields_set
    changes: dict[str, object] = {}

    if "amount" in sent:
        if body.amount is None:
            raise HTTPException(status_code=422, detail="Inserisci un importo.")
        changes["amount_cents"] = _amount(body.amount)
    if "category" in sent:
        if body.category is None:
            raise HTTPException(status_code=422, detail="Scegli una categoria.")
        # The sale of a Vinted item stays a Vinted income (section totals).
        if current["vinted_item_id"] is not None and body.category != current["category"]:
            raise HTTPException(
                status_code=409,
                detail=f"È la vendita dell'articolo Vinted «{current['vinted_item_title']}»: "
                "la categoria resta Vinted.",
            )
        changes["category"] = body.category
    if "income_date" in sent:
        if body.income_date is None:
            raise HTTPException(status_code=422, detail="Inserisci una data.")
        check_expense_date(body.income_date)
        changes["income_date"] = body.income_date.isoformat()
    if "received_by_user_id" in sent:
        if body.received_by_user_id is None:
            raise HTTPException(status_code=422, detail="Indica chi ha ricevuto l'entrata.")
        _check_user(db, body.received_by_user_id)
        changes["received_by_user_id"] = body.received_by_user_id
    if "note" in sent:
        changes["note"] = _clean_note(body.note)

    if changes:
        changes["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in changes)
        db.execute(
            f"UPDATE incomes SET {assignments} WHERE id = ?", (*changes.values(), income_id)
        )
        db.commit()
    return fetch_income(db, income_id)


@router.delete("/{income_id}", status_code=204)
def delete_income(
    income_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    fetch_income(db, income_id)
    db.execute("DELETE FROM incomes WHERE id = ?", (income_id,))
    db.commit()
