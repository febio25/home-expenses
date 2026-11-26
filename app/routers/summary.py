"""Monthly summary: totals per category, incomes and the difference, plus the
month-by-month totals behind the small chart. Nothing fancier, by design:
the real analysis happens on the exported CSV.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from fractions import Fraction

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dates import add_months, month_bounds, resolve_range
from ..db import get_db
from ..schemas import (
    INCOME_CATEGORIES,
    IncomeSummaryOut,
    MonthTotals,
    PeriodTotalsOut,
    RecurringCostsOut,
    SearchTotalsOut,
    SummaryOut,
)
from ..security import current_user
from ..text import MAX_QUERY_LENGTH
from .expenses import EXPENSE_SELECT, expense_filters
from .incomes import INCOME_SELECT, income_filters

router = APIRouter(prefix="/summary", tags=["summary"], dependencies=[Depends(current_user)])

# Meal vouchers are an income category: their part is shown on its own.
VOUCHER_CATEGORY = "meal_voucher"


@router.get("", response_model=SummaryOut)
def monthly_summary(
    month: str = Query(..., description="YYYY-MM"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Expenses of the month (``total_cents``, by category) and its incomes.

    ``balance_cents`` is incomes minus expenses. With no income recorded in
    the month it is simply minus the expenses: the app then shows no
    difference at all (``income_count`` is 0).
    """
    start, end = month_bounds(month)
    rows = db.execute(
        "SELECT c.id AS category_id, c.name AS category_name,"
        "       SUM(e.amount_cents) AS total_cents, COUNT(*) AS expense_count"
        "  FROM expenses e JOIN categories c ON c.id = e.category_id"
        " WHERE e.expense_date >= ? AND e.expense_date <= ?"
        " GROUP BY c.id ORDER BY total_cents DESC, c.sort_order",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    by_category = [dict(row) for row in rows]
    income = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS cents, COUNT(*) AS count,"
        "       COALESCE(SUM(CASE WHEN category = ? THEN amount_cents END), 0) AS vouchers"
        "  FROM incomes WHERE income_date >= ? AND income_date <= ?",
        (VOUCHER_CATEGORY, start.isoformat(), end.isoformat()),
    ).fetchone()
    total = sum(row["total_cents"] for row in by_category)
    expected = expected_incomes(db, start, end)
    return {
        "month": month,
        "total_cents": total,
        "expense_count": sum(row["expense_count"] for row in by_category),
        "by_category": by_category,
        "income_cents": income["cents"],
        "income_count": income["count"],
        "voucher_cents": income["vouchers"],
        "balance_cents": income["cents"] - total,
        "expected_income_cents": sum(item["amount_cents"] for item in expected),
        "expected_incomes": expected,
    }


def expected_incomes(db: sqlite3.Connection, start: date, end: date) -> list[dict]:
    """Active recurring incomes whose next due date falls in [start, end]:
    salaries and the like that the month will still bring (0.14.0). Until
    the salary is registered, "incomes minus expenses" of the month in
    progress is far below zero; the app shows these next to it.

    A template's next_due is the first occurrence not registered yet, and
    templates repeat every month at most often, so each one counts once.
    """
    rows = db.execute(
        "SELECT r.id AS recurring_id, r.category, u.display_name AS received_by_name,"
        "       r.next_due AS due_date, r.amount_cents"
        "  FROM recurring_incomes r JOIN users u ON u.id = r.received_by_user_id"
        " WHERE r.is_active = 1 AND r.next_due >= ? AND r.next_due <= ?"
        " ORDER BY r.next_due, r.id",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [
        {**dict(row), "category_name": INCOME_CATEGORIES.get(row["category"], row["category"])}
        for row in rows
    ]


def _search_totals(db: sqlite3.Connection, select: str, where: str, params: list, date_column: str) -> dict:
    """Count and total of every row a search finds, also per month, newest
    month first. ``select`` is the list's own SELECT, so the joins the
    search looks into (merchant, category, Vinted item) are the same."""
    rows = db.execute(
        f"SELECT substr(sub.day, 1, 7) AS month, COUNT(*) AS count, SUM(sub.cents) AS total_cents"
        f"  FROM (SELECT {date_column} AS day, amount_cents AS cents FROM ({select}{where})) sub"
        f" GROUP BY 1 ORDER BY 1 DESC",
        params,
    ).fetchall()
    months = [dict(row) for row in rows]
    return {
        "count": sum(row["count"] for row in months),
        "total_cents": sum(row["total_cents"] for row in months),
        "months": months,
    }


@router.get("/search/expenses", response_model=SearchTotalsOut)
def search_expense_totals(
    q: str = Query(..., min_length=1, max_length=MAX_QUERY_LENGTH, description="As in GET /expenses"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Totals of a search in "Movimenti" over every month (0.14.0): the list
    comes a page at a time from GET /expenses?q=…&limit=…&offset=…"""
    where, params = expense_filters(None, None, None, None, q)
    return _search_totals(db, EXPENSE_SELECT, where, params, "expense_date")


@router.get("/search/incomes", response_model=SearchTotalsOut)
def search_income_totals(
    q: str = Query(..., min_length=1, max_length=MAX_QUERY_LENGTH, description="As in GET /incomes"),
    db: sqlite3.Connection = Depends(get_db),
):
    """The same as /summary/search/expenses, for the incomes."""
    where, params = income_filters(None, None, None, q)
    return _search_totals(db, INCOME_SELECT, where, params, "income_date")


def _cents(value: Fraction) -> int:
    """A fraction of a cent rounded half up: 1/3 of 1000 cents is 333."""
    return int(value + Fraction(1, 2)) if value >= 0 else -int(-value + Fraction(1, 2))


def _recurring_side(db: sqlite3.Connection, table: str) -> dict:
    rows = db.execute(
        f"SELECT amount_cents, interval_months, is_variable FROM {table} WHERE is_active = 1"
    ).fetchall()
    # Exact fractions, rounded once at the end: three items every 3 months
    # of 1,00 € each make 1,00 € a month, not 0,99 €.
    month = sum((Fraction(row["amount_cents"], row["interval_months"]) for row in rows), Fraction(0))
    return {
        "count": len(rows),
        "month_cents": _cents(month),
        "year_cents": _cents(month * 12),
        "has_variable": any(row["is_variable"] for row in rows),
    }


@router.get("/recurring", response_model=RecurringCostsOut)
def recurring_costs(db: sqlite3.Connection = Depends(get_db)):
    """0.17.0: what the active recurring expenses cost, and the active
    recurring incomes bring, a month and a year. An item every 2 months
    counts half a month, a yearly one a twelfth. Suspended items are left
    out. ``has_variable``: some amounts are estimates (the app writes «~»)."""
    return {
        "expenses": _recurring_side(db, "recurring_expenses"),
        "incomes": _recurring_side(db, "recurring_incomes"),
    }


@router.get("/incomes", response_model=IncomeSummaryOut)
def income_summary(
    month: str = Query(..., description="YYYY-MM"),
    db: sqlite3.Connection = Depends(get_db),
):
    """The incomes of the month by category, largest first (the pie chart
    of the incomes screen)."""
    start, end = month_bounds(month)
    rows = db.execute(
        "SELECT category, SUM(amount_cents) AS total_cents, COUNT(*) AS income_count"
        "  FROM incomes WHERE income_date >= ? AND income_date <= ?"
        " GROUP BY category ORDER BY total_cents DESC, category",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    by_category = [
        {**dict(row), "category_name": INCOME_CATEGORIES.get(row["category"], row["category"])}
        for row in rows
    ]
    return {
        "month": month,
        "total_cents": sum(row["total_cents"] for row in by_category),
        "income_count": sum(row["income_count"] for row in by_category),
        "by_category": by_category,
    }


@router.get("/period", response_model=PeriodTotalsOut)
def period_summary(
    date_from: date = Query(..., alias="from", description="First day, YYYY-MM-DD"),
    date_to: date = Query(..., alias="to", description="Last day, YYYY-MM-DD, included"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Incomes, expenses and their difference over any period: a month, a
    year, the last six months or two dates of one's choice ("Esplora",
    0.9.0). Only totals: no categories, no list."""
    start, end = resolve_range(None, date_from, date_to)
    window = (start.isoformat(), end.isoformat())
    spent = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS cents, COUNT(*) AS count"
        "  FROM expenses WHERE expense_date >= ? AND expense_date <= ?",
        window,
    ).fetchone()
    income = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS cents, COUNT(*) AS count,"
        "       COALESCE(SUM(CASE WHEN category = ? THEN amount_cents END), 0) AS vouchers"
        "  FROM incomes WHERE income_date >= ? AND income_date <= ?",
        (VOUCHER_CATEGORY, *window),
    ).fetchone()
    return {
        "start": start,
        "end": end,
        "income_cents": income["cents"],
        "income_count": income["count"],
        "voucher_cents": income["vouchers"],
        "expense_cents": spent["cents"],
        "expense_count": spent["count"],
        "balance_cents": income["cents"] - spent["cents"],
    }


def _month_key(day) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def trend_skeleton(month: str, months: int) -> tuple[date, date, dict[str, dict]]:
    """First and last day of a window of ``months`` months ending with
    ``month``, and one all-zero entry per month, oldest first. Shared with
    the trend of the Vinted section."""
    first_day, last_day = month_bounds(month)
    try:
        start = add_months(first_day, -(months - 1), 1)
    except ValueError as error:  # a window reaching before year 1
        raise HTTPException(status_code=422, detail="Mese non valido.") from error
    totals = {}
    for offset in range(months):
        key = _month_key(add_months(start, offset, 1))
        totals[key] = {
            "month": key, "income_cents": 0, "income_count": 0,
            "expense_cents": 0, "expense_count": 0, "voucher_cents": 0,
        }
    return start, last_day, totals


@router.get("/trend", response_model=list[MonthTotals])
def monthly_trend(
    month: str = Query(..., description="Last month of the window, YYYY-MM"),
    months: int = Query(6, ge=1, le=24, description="How many months, ending with `month`"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Incomes and expenses of each month in the window, oldest first.

    Every month of the window is listed, with zeros where nothing was
    recorded, so a chart can draw one slot per month.
    """
    start, last_day, totals = trend_skeleton(month, months)
    window = (start.isoformat(), last_day.isoformat())
    for table, column, prefix in (
        ("expenses", "expense_date", "expense"),
        ("incomes", "income_date", "income"),
    ):
        rows = db.execute(
            f"SELECT substr({column}, 1, 7) AS month, SUM(amount_cents) AS cents, COUNT(*) AS count"
            f"  FROM {table} WHERE {column} >= ? AND {column} <= ? GROUP BY 1",
            window,
        ).fetchall()
        for row in rows:
            totals[row["month"]][f"{prefix}_cents"] = row["cents"]
            totals[row["month"]][f"{prefix}_count"] = row["count"]

    rows = db.execute(
        "SELECT substr(income_date, 1, 7) AS month, SUM(amount_cents) AS cents FROM incomes"
        " WHERE category = ? AND income_date >= ? AND income_date <= ? GROUP BY 1",
        (VOUCHER_CATEGORY, *window),
    ).fetchall()
    for row in rows:
        totals[row["month"]]["voucher_cents"] = row["cents"]

    for item in totals.values():
        item["balance_cents"] = item["income_cents"] - item["expense_cents"]
    return list(totals.values())
