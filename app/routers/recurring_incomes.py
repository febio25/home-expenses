"""Recurring income templates: list, create, edit, delete, register, skip.

The twin of the recurring expense templates (routers/recurring.py), with
the same rules: a template never writes incomes on its own. The client
shows the templates whose ``next_due`` is today or earlier as "da
registrare"; registering one creates a normal income and moves
``next_due`` forward by ``interval_months``. Skipping moves it forward
without an income. A table of its own, so the expense templates and their
endpoints stay exactly as they were.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response

from ..dates import add_months, due_day_after_change
from ..db import get_db, utc_now
from ..money import format_cents
from ..schemas import (
    INCOME_CATEGORIES,
    IncomeCreate,
    RecurringIncomeCreate,
    RecurringIncomeOut,
    RecurringIncomeRegister,
    RecurringIncomeRegistered,
    RecurringIncomeUpdate,
    RecurringOccurrence,
)
from ..security import current_user
from .expenses import _amount, _check_user, _clean_note
from .incomes import fetch_income, insert_income

router = APIRouter(
    prefix="/recurring-incomes", tags=["recurring incomes"], dependencies=[Depends(current_user)]
)

_SELECT = """
SELECT r.id, r.amount_cents, r.category, r.note,
       r.received_by_user_id, u.display_name AS received_by_name,
       r.interval_months, r.day_of_month, r.next_due, r.is_active
  FROM recurring_incomes r
  JOIN users u ON u.id = r.received_by_user_id
"""


def _out(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["category_name"] = INCOME_CATEGORIES.get(data["category"], data["category"])
    return data


def _fetch(db: sqlite3.Connection, recurring_id: int) -> dict:
    row = db.execute(f"{_SELECT} WHERE r.id = ?", (recurring_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Entrata ricorrente non trovata.")
    return _out(row)


def _advance(db: sqlite3.Connection, template: dict) -> None:
    current = date.fromisoformat(str(template["next_due"]))
    following = add_months(current, template["interval_months"], template["day_of_month"])
    db.execute(
        "UPDATE recurring_incomes SET next_due = ?, updated_at = ? WHERE id = ?",
        (following.isoformat(), utc_now(), template["id"]),
    )


def _check_occurrence(template: dict, body: RecurringOccurrence) -> None:
    if not template["is_active"]:
        raise HTTPException(status_code=409, detail="Questa entrata ricorrente è sospesa.")
    if body.due_date.isoformat() != str(template["next_due"]):
        raise HTTPException(
            status_code=409,
            detail="Questa scadenza è già stata registrata o saltata. Aggiorna la pagina.",
        )


@router.get("", response_model=list[RecurringIncomeOut])
def list_recurring_incomes(db: sqlite3.Connection = Depends(get_db)):
    """All templates, the next to fall due first. Suspended ones last."""
    rows = db.execute(f"{_SELECT} ORDER BY r.is_active DESC, r.next_due, r.id").fetchall()
    return [_out(row) for row in rows]


@router.post("", response_model=RecurringIncomeOut, status_code=201)
def create_recurring_income(
    body: RecurringIncomeCreate,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    amount_cents = _amount(body.amount)
    received_by = body.received_by_user_id if body.received_by_user_id is not None else user["id"]
    _check_user(db, received_by)
    now = utc_now()
    cursor = db.execute(
        "INSERT INTO recurring_incomes (amount_cents, category, note, received_by_user_id,"
        " interval_months, day_of_month, next_due, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            amount_cents,
            body.category,
            _clean_note(body.note),
            received_by,
            body.interval_months,
            body.next_due.day,
            body.next_due.isoformat(),
            now,
            now,
        ),
    )
    db.commit()
    return _fetch(db, cursor.lastrowid)


@router.get("/{recurring_id}", response_model=RecurringIncomeOut)
def get_recurring_income(recurring_id: int, db: sqlite3.Connection = Depends(get_db)):
    return _fetch(db, recurring_id)


@router.patch("/{recurring_id}", response_model=RecurringIncomeOut)
def update_recurring_income(
    recurring_id: int, body: RecurringIncomeUpdate, db: sqlite3.Connection = Depends(get_db)
):
    """Change only the fields present. ``note: null`` clears the note."""
    current = _fetch(db, recurring_id)
    sent = body.model_fields_set
    required = {
        "amount": "Inserisci un importo.",
        "category": "Scegli una categoria.",
        "received_by_user_id": "Indica chi riceve l'entrata.",
        "interval_months": "Indica ogni quanti mesi.",
        "next_due": "Inserisci la prossima scadenza.",
        "is_active": "Indica se è attiva.",
    }
    for field, message in required.items():
        if field in sent and getattr(body, field) is None:
            raise HTTPException(status_code=422, detail=message)

    changes: dict[str, object] = {}
    if "amount" in sent:
        changes["amount_cents"] = _amount(body.amount)
    if "category" in sent:
        changes["category"] = body.category
    if "note" in sent:
        changes["note"] = _clean_note(body.note)
    if "received_by_user_id" in sent:
        _check_user(db, body.received_by_user_id)
        changes["received_by_user_id"] = body.received_by_user_id
    if "interval_months" in sent:
        changes["interval_months"] = body.interval_months
    if "next_due" in sent:
        changes["next_due"] = body.next_due.isoformat()
        changes["day_of_month"] = due_day_after_change(body.next_due, current["day_of_month"])
    if "is_active" in sent:
        changes["is_active"] = int(body.is_active)

    if changes:
        changes["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in changes)
        db.execute(
            f"UPDATE recurring_incomes SET {assignments} WHERE id = ?",
            (*changes.values(), recurring_id),
        )
        db.commit()
    return _fetch(db, recurring_id)


@router.delete("/{recurring_id}", status_code=204)
def delete_recurring_income(recurring_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Delete the template only: incomes already registered stay."""
    _fetch(db, recurring_id)
    db.execute("DELETE FROM recurring_incomes WHERE id = ?", (recurring_id,))
    db.commit()
    return Response(status_code=204)


@router.post(
    "/{recurring_id}/register", response_model=RecurringIncomeRegistered, status_code=201
)
def register_recurring_income(
    recurring_id: int,
    body: RecurringIncomeRegister,
    response: Response,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Record the due occurrence as an income and move ``next_due`` forward.

    Fields left out come from the template. Retrying with the same
    ``client_uuid`` returns the income already saved (status 200) and does
    not move the date twice.
    """
    template = _fetch(db, recurring_id)
    if body.client_uuid:
        existing = db.execute(
            "SELECT id FROM incomes WHERE client_uuid = ?", (body.client_uuid,)
        ).fetchone()
        if existing is not None:
            response.status_code = 200
            return {"income": fetch_income(db, existing["id"]), "recurring": template}
    _check_occurrence(template, body)
    category = body.category if body.category is not None else template["category"]
    if category not in INCOME_CATEGORIES:  # a code dropped from the list in a later version
        raise HTTPException(
            status_code=409,
            detail="La categoria di questa entrata ricorrente non esiste più: scegline un'altra.",
        )

    sent = body.model_fields_set
    income = IncomeCreate(
        amount=body.amount if body.amount is not None else format_cents(template["amount_cents"]),
        category=category,
        income_date=body.income_date or body.due_date,
        note=body.note if "note" in sent else template["note"],
        received_by_user_id=body.received_by_user_id or template["received_by_user_id"],
        client_uuid=body.client_uuid,
    )
    income_id, created = insert_income(db, user, income)
    if created:
        _advance(db, template)
        db.commit()
    else:
        response.status_code = 200
    return {"income": fetch_income(db, income_id), "recurring": _fetch(db, recurring_id)}


@router.post("/{recurring_id}/skip", response_model=RecurringIncomeOut)
def skip_recurring_income(
    recurring_id: int, body: RecurringOccurrence, db: sqlite3.Connection = Depends(get_db)
):
    """Skip the due occurrence (not received this time): no income is created."""
    template = _fetch(db, recurring_id)
    _check_occurrence(template, body)
    _advance(db, template)
    db.commit()
    return _fetch(db, recurring_id)
