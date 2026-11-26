"""Recurring expense templates: list, create, edit, delete, register, skip.

A template never writes expenses on its own. The client shows the templates
whose ``next_due`` is today or earlier as "da registrare"; registering one
creates a normal expense and moves ``next_due`` forward by
``interval_months``. Skipping moves it forward without an expense.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response

from ..dates import add_months, due_day_after_change
from ..db import get_db, utc_now
from ..schemas import (
    ExpenseCreate,
    RecurringCreate,
    RecurringOccurrence,
    RecurringOut,
    RecurringRegister,
    RecurringRegistered,
    RecurringUpdate,
)
from ..security import current_user
from ..validation import check_category, check_user, clean_note, require_amount
from .expenses import fetch_expense, insert_expense
from .merchants import clean_merchant_name

router = APIRouter(prefix="/recurring", tags=["recurring"], dependencies=[Depends(current_user)])

_SELECT = """
SELECT r.id, r.amount_cents, r.category_id, c.name AS category_name,
       c.is_active AS category_active, r.merchant_name, r.note,
       r.paid_by_user_id, u.display_name AS paid_by_name, r.payment_method,
       r.interval_months, r.day_of_month, r.next_due, r.is_active, r.is_variable
  FROM recurring_expenses r
  JOIN categories c ON c.id = r.category_id
  JOIN users u ON u.id = r.paid_by_user_id
"""


def _fetch(db: sqlite3.Connection, recurring_id: int) -> dict:
    row = db.execute(f"{_SELECT} WHERE r.id = ?", (recurring_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Spesa ricorrente non trovata.")
    return dict(row)


def _advance(db: sqlite3.Connection, template: dict) -> None:
    current = date.fromisoformat(str(template["next_due"]))
    following = add_months(current, template["interval_months"], template["day_of_month"])
    db.execute(
        "UPDATE recurring_expenses SET next_due = ?, updated_at = ? WHERE id = ?",
        (following.isoformat(), utc_now(), template["id"]),
    )


def _cents_text(cents: int) -> str:
    """12345 -> "123.45", without going through float."""
    return f"{cents // 100}.{cents % 100:02d}"


def _check_occurrence(template: dict, body: RecurringOccurrence) -> None:
    if not template["is_active"]:
        raise HTTPException(status_code=409, detail="Questa spesa ricorrente è sospesa.")
    if body.due_date.isoformat() != str(template["next_due"]):
        raise HTTPException(
            status_code=409,
            detail="Questa scadenza è già stata registrata o saltata. Aggiorna la pagina.",
        )


@router.get("", response_model=list[RecurringOut])
def list_recurring(db: sqlite3.Connection = Depends(get_db)):
    """All templates, the next to fall due first. Suspended ones last."""
    rows = db.execute(f"{_SELECT} ORDER BY r.is_active DESC, r.next_due, r.id").fetchall()
    return [dict(row) for row in rows]


@router.post("", response_model=RecurringOut, status_code=201)
def create_recurring(
    body: RecurringCreate,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    amount_cents = require_amount(body.amount)
    check_category(db, body.category_id, must_be_active=True)
    paid_by = body.paid_by_user_id if body.paid_by_user_id is not None else user["id"]
    check_user(db, paid_by)
    now = utc_now()
    cursor = db.execute(
        "INSERT INTO recurring_expenses (amount_cents, category_id, merchant_name, note,"
        " paid_by_user_id, payment_method, interval_months, day_of_month, next_due,"
        " is_variable, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            amount_cents,
            body.category_id,
            clean_merchant_name(body.merchant),
            clean_note(body.note),
            paid_by,
            body.payment_method,
            body.interval_months,
            body.next_due.day,
            body.next_due.isoformat(),
            int(body.is_variable),
            now,
            now,
        ),
    )
    db.commit()
    return _fetch(db, cursor.lastrowid)


@router.get("/{recurring_id}", response_model=RecurringOut)
def get_recurring(recurring_id: int, db: sqlite3.Connection = Depends(get_db)):
    return _fetch(db, recurring_id)


@router.patch("/{recurring_id}", response_model=RecurringOut)
def update_recurring(
    recurring_id: int, body: RecurringUpdate, db: sqlite3.Connection = Depends(get_db)
):
    """Change only the fields present. ``merchant: null`` and ``note: null`` clear them."""
    current = _fetch(db, recurring_id)
    sent = body.model_fields_set
    changes: dict[str, object] = {}
    required = {
        "amount": "Inserisci un importo.",
        "category_id": "Scegli una categoria.",
        "paid_by_user_id": "Indica chi paga.",
        "payment_method": "Scegli un metodo di pagamento.",
        "interval_months": "Indica ogni quanti mesi.",
        "next_due": "Inserisci la prossima scadenza.",
        "is_active": "Indica se è attiva.",
        "is_variable": "Indica se l'importo è variabile.",
    }
    for field, message in required.items():
        if field in sent and getattr(body, field) is None:
            raise HTTPException(status_code=422, detail=message)

    if "amount" in sent:
        changes["amount_cents"] = require_amount(body.amount)
    if "category_id" in sent:
        check_category(
            db, body.category_id, must_be_active=body.category_id != current["category_id"]
        )
        changes["category_id"] = body.category_id
    if "merchant" in sent:
        changes["merchant_name"] = clean_merchant_name(body.merchant)
    if "note" in sent:
        changes["note"] = clean_note(body.note)
    if "paid_by_user_id" in sent:
        check_user(db, body.paid_by_user_id)
        changes["paid_by_user_id"] = body.paid_by_user_id
    if "payment_method" in sent:
        changes["payment_method"] = body.payment_method
    if "interval_months" in sent:
        changes["interval_months"] = body.interval_months
    if "next_due" in sent:
        changes["next_due"] = body.next_due.isoformat()
        changes["day_of_month"] = due_day_after_change(body.next_due, current["day_of_month"])
    if "is_active" in sent:
        changes["is_active"] = int(body.is_active)
    if "is_variable" in sent:
        changes["is_variable"] = int(body.is_variable)

    if changes:
        changes["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in changes)
        db.execute(
            f"UPDATE recurring_expenses SET {assignments} WHERE id = ?",
            (*changes.values(), recurring_id),
        )
        db.commit()
    return _fetch(db, recurring_id)


@router.delete("/{recurring_id}", status_code=204)
def delete_recurring(recurring_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Delete the template only: expenses already registered stay."""
    _fetch(db, recurring_id)
    db.execute("DELETE FROM recurring_expenses WHERE id = ?", (recurring_id,))
    db.commit()
    return Response(status_code=204)


@router.post("/{recurring_id}/register", response_model=RecurringRegistered, status_code=201)
def register_recurring(
    recurring_id: int,
    body: RecurringRegister,
    response: Response,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Record the due occurrence as an expense and move ``next_due`` forward.

    Fields left out come from the template. Retrying with the same
    ``client_uuid`` returns the expense already saved (status 200) and does
    not move the date twice.
    """
    template = _fetch(db, recurring_id)
    if body.client_uuid:
        existing = db.execute(
            "SELECT id FROM expenses WHERE client_uuid = ?", (body.client_uuid,)
        ).fetchone()
        if existing is not None:
            response.status_code = 200
            return {"expense": fetch_expense(db, existing["id"]), "recurring": template}
    _check_occurrence(template, body)
    if "category_id" not in body.model_fields_set and not template["category_active"]:
        raise HTTPException(
            status_code=409,
            detail="La categoria di questa spesa ricorrente è disattivata: scegline un'altra.",
        )

    sent = body.model_fields_set
    expense = ExpenseCreate(
        amount=body.amount if body.amount is not None else _cents_text(template["amount_cents"]),
        category_id=body.category_id if body.category_id is not None else template["category_id"],
        merchant=body.merchant if "merchant" in sent else template["merchant_name"],
        note=body.note if "note" in sent else template["note"],
        expense_date=body.expense_date or body.due_date,
        paid_by_user_id=body.paid_by_user_id or template["paid_by_user_id"],
        payment_method=body.payment_method or template["payment_method"],
        client_uuid=body.client_uuid,
    )
    expense_id, created = insert_expense(db, user, expense)
    if created:
        _advance(db, template)
        db.commit()
    else:
        response.status_code = 200
    return {"expense": fetch_expense(db, expense_id), "recurring": _fetch(db, recurring_id)}


@router.post("/{recurring_id}/skip", response_model=RecurringOut)
def skip_recurring(
    recurring_id: int, body: RecurringOccurrence, db: sqlite3.Connection = Depends(get_db)
):
    """Skip the due occurrence (not charged this time): no expense is created."""
    template = _fetch(db, recurring_id)
    _check_occurrence(template, body)
    _advance(db, template)
    db.commit()
    return _fetch(db, recurring_id)
