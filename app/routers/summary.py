"""Monthly summary: totals per category, incomes and the difference, plus the
month-by-month totals behind the small chart. Nothing fancier, by design:
the real analysis happens on the exported CSV.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dates import add_months, month_bounds, resolve_range
from ..db import get_db
from ..schemas import INCOME_CATEGORIES, IncomeSummaryOut, MonthTotals, PeriodTotalsOut, SummaryOut
from ..security import current_user

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
    return {
        "month": month,
        "total_cents": total,
        "expense_count": sum(row["expense_count"] for row in by_category),
        "by_category": by_category,
        "income_cents": income["cents"],
        "income_count": income["count"],
        "voucher_cents": income["vouchers"],
        "balance_cents": income["cents"] - total,
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
