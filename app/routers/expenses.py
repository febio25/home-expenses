"""Expenses: create, list, edit, delete."""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..dates import check_expense_date, range_filter, resolve_range
from ..db import get_db, utc_now
from ..money import AmountError, parse_amount
from ..schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate
from ..security import current_user
from ..text import MAX_QUERY_LENGTH, clean_query, search_clause
from .merchants import get_or_create_merchant, prune_merchant

router = APIRouter(prefix="/expenses", tags=["expenses"])

EXPENSE_SELECT = """
SELECT e.id, e.amount_cents, e.expense_date,
       e.category_id, c.name AS category_name,
       e.merchant_id, m.name AS merchant_name,
       e.note,
       e.paid_by_user_id, payer.display_name AS paid_by_name,
       e.payment_method,
       e.created_by_user_id, author.display_name AS created_by_name,
       e.created_at, e.updated_at,
       v.id AS vinted_item_id, v.title AS vinted_item_title
  FROM expenses e
  JOIN categories c ON c.id = e.category_id
  LEFT JOIN merchants m ON m.id = e.merchant_id
  JOIN users payer ON payer.id = e.paid_by_user_id
  JOIN users author ON author.id = e.created_by_user_id
  LEFT JOIN vinted_items v ON v.purchase_expense_id = e.id
"""


def _fetch(db: sqlite3.Connection, expense_id: int) -> sqlite3.Row:
    row = db.execute(f"{EXPENSE_SELECT} WHERE e.id = ?", (expense_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Spesa non trovata.")
    return row


def _amount(text: str) -> int:
    try:
        return parse_amount(text)
    except AmountError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _check_category(db: sqlite3.Connection, category_id: int, must_be_active: bool) -> None:
    row = db.execute(
        "SELECT is_active FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail="Categoria non valida.")
    if must_be_active and not row["is_active"]:
        raise HTTPException(status_code=422, detail="Questa categoria è disattivata.")


def _check_user(db: sqlite3.Connection, user_id: int) -> None:
    if db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
        raise HTTPException(status_code=422, detail="Utente non valido.")


def _clean_note(note: str | None) -> str | None:
    if note is None:
        return None
    return note.strip() or None


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    month: str | None = Query(None, description="YYYY-MM; wins over from/to"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    category_id: int | None = Query(None, description="Only expenses of this category"),
    q: str | None = Query(
        None, max_length=MAX_QUERY_LENGTH,
        description="Text to find in merchant, note, category or linked Vinted item, "
        "without case or accents; or an amount (\"12,50\")",
    ),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Expenses in the range, newest first. Without parameters: all of them.

    With ``category_id``, only that category (used by the summary to show
    what makes up a category total). An unknown id gives an empty list.
    With ``q`` (0.9.0), only the expenses that match it: the search of
    "Movimenti", over every month unless a range is given too.
    """
    start, end = resolve_range(month, date_from, date_to)
    where, params = range_filter(start, end)
    conditions = [where.removeprefix(" WHERE ")] if where else []
    if category_id is not None:
        conditions.append("e.category_id = ?")
        params.append(category_id)
    text = clean_query(q)
    if text:
        clause, clause_params = search_clause(
            text, ["m.name", "e.note", "c.name", "v.title"], "e.amount_cents"
        )
        conditions.append(clause)
        params.extend(clause_params)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = db.execute(
        f"{EXPENSE_SELECT}{where} ORDER BY e.expense_date DESC, e.id DESC", params
    ).fetchall()
    return [dict(row) for row in rows]


def insert_expense(
    db: sqlite3.Connection, user: sqlite3.Row, body: ExpenseCreate, *, planned: bool = False
) -> tuple[int, bool]:
    """Insert an expense without committing. Returns (id, created).

    With a ``client_uuid`` already known, nothing is inserted and the id of
    the existing expense is returned with ``created`` False. Also used when
    registering a recurring expense, inside the same transaction.

    ``planned`` lets the date run up to a year ahead (see ``dates``): only
    "Nuova spesa" asks for it. A recurring registration and the purchase of
    a Vinted item are things that already happened.
    """
    if body.client_uuid:
        existing = db.execute(
            "SELECT id FROM expenses WHERE client_uuid = ?", (body.client_uuid,)
        ).fetchone()
        if existing is not None:
            return existing["id"], False

    amount_cents = _amount(body.amount)
    check_expense_date(body.expense_date, planned=planned)
    _check_category(db, body.category_id, must_be_active=True)
    paid_by = body.paid_by_user_id if body.paid_by_user_id is not None else user["id"]
    _check_user(db, paid_by)

    now = utc_now()
    merchant_id = get_or_create_merchant(db, body.merchant)
    try:
        cursor = db.execute(
            "INSERT INTO expenses (client_uuid, amount_cents, expense_date, category_id,"
            " merchant_id, note, paid_by_user_id, payment_method, created_by_user_id,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                body.client_uuid,
                amount_cents,
                body.expense_date.isoformat(),
                body.category_id,
                merchant_id,
                _clean_note(body.note),
                paid_by,
                body.payment_method,
                user["id"],
                now,
                now,
            ),
        )
    except sqlite3.IntegrityError:
        # Two identical retries raced: the other one won, return its row.
        db.rollback()
        existing = db.execute(
            "SELECT id FROM expenses WHERE client_uuid = ?", (body.client_uuid,)
        ).fetchone()
        if existing is None:
            raise
        return existing["id"], False
    return cursor.lastrowid, True


def fetch_expense(db: sqlite3.Connection, expense_id: int) -> dict:
    return dict(_fetch(db, expense_id))


@router.post("", response_model=ExpenseOut, status_code=201)
def create_expense(
    body: ExpenseCreate,
    response: Response,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Record an expense.

    Retrying with the same ``client_uuid`` (for example after a dropped
    connection) returns the expense already saved, with status 200.
    """
    expense_id, created = insert_expense(db, user, body, planned=True)
    if created:
        db.commit()
    else:
        response.status_code = 200
    return dict(_fetch(db, expense_id))


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(
    expense_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return dict(_fetch(db, expense_id))


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    body: ExpenseUpdate,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Change only the fields present in the body.

    Send ``"merchant": null`` or ``"note": null`` to clear those fields.
    """
    current = _fetch(db, expense_id)
    sent = body.model_fields_set
    changes: dict[str, object] = {}

    if "amount" in sent:
        if body.amount is None:
            raise HTTPException(status_code=422, detail="Inserisci un importo.")
        changes["amount_cents"] = _amount(body.amount)
    if "category_id" in sent:
        if body.category_id is None:
            raise HTTPException(status_code=422, detail="Scegli una categoria.")
        # Keeping an inactive category on an old expense is allowed.
        _check_category(
            db, body.category_id, must_be_active=body.category_id != current["category_id"]
        )
        # The purchase of a Vinted item stays in the Vinted category, or it
        # would drop out of the section's totals.
        if current["vinted_item_id"] is not None and body.category_id != current["category_id"]:
            raise HTTPException(
                status_code=409,
                detail=f"È l'acquisto dell'articolo Vinted «{current['vinted_item_title']}»: "
                "la categoria resta Vinted.",
            )
        changes["category_id"] = body.category_id
    if "expense_date" in sent:
        if body.expense_date is None:
            raise HTTPException(status_code=422, detail="Inserisci una data.")
        # The purchase of a Vinted item cannot be in the future.
        check_expense_date(body.expense_date, planned=current["vinted_item_id"] is None)
        changes["expense_date"] = body.expense_date.isoformat()
    if "paid_by_user_id" in sent:
        if body.paid_by_user_id is None:
            raise HTTPException(status_code=422, detail="Indica chi ha pagato.")
        _check_user(db, body.paid_by_user_id)
        changes["paid_by_user_id"] = body.paid_by_user_id
    if "payment_method" in sent:
        if body.payment_method is None:
            raise HTTPException(status_code=422, detail="Scegli un metodo di pagamento.")
        changes["payment_method"] = body.payment_method
    if "note" in sent:
        changes["note"] = _clean_note(body.note)
    if "merchant" in sent:
        changes["merchant_id"] = get_or_create_merchant(db, body.merchant)

    if changes:
        changes["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in changes)
        db.execute(
            f"UPDATE expenses SET {assignments} WHERE id = ?",
            (*changes.values(), expense_id),
        )
        if "merchant_id" in changes and changes["merchant_id"] != current["merchant_id"]:
            prune_merchant(db, current["merchant_id"])
        db.commit()
    return dict(_fetch(db, expense_id))


@router.delete("/{expense_id}", status_code=204)
def delete_expense(
    expense_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    current = _fetch(db, expense_id)
    db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    prune_merchant(db, current["merchant_id"])
    db.commit()
