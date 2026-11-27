"""Vinted section: the summary (0.8.0): sales, Vinted expenses and their
difference for a month, a period or the last months, the gain on the items
sold and the yearly count against the DAC7 thresholds. Split from
vinted.py in 0.17.0; same addresses."""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Query

from ..dates import month_bounds, resolve_range
from ..db import get_db
from ..schemas import MonthTotals
from ..security import current_user
from ..vinted_schemas import VintedPeriodOut, VintedSummaryOut
from .summary import trend_skeleton
from .vinted import VINTED

router = APIRouter(prefix="/vinted", tags=["vinted"])


def _section_totals(db: sqlite3.Connection, start: date, end: date) -> dict:
    """Sales, Vinted expenses (purchases and extras) and their difference
    between two dates; the items sold in them, with what they cost."""
    window = (start.isoformat(), end.isoformat())
    sales = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS cents, COUNT(*) AS count FROM incomes"
        " WHERE category = ? AND income_date >= ? AND income_date <= ?",
        (VINTED, *window),
    ).fetchone()
    spent = db.execute(
        "SELECT COALESCE(SUM(e.amount_cents), 0) AS cents, COUNT(*) AS count,"
        "       COALESCE(SUM(v.id IS NOT NULL), 0) AS purchases,"
        "       COALESCE(SUM(CASE WHEN v.id IS NOT NULL THEN e.amount_cents END), 0) AS purchase_cents"
        "  FROM expenses e"
        "  JOIN categories c ON c.id = e.category_id AND c.system_key = ?"
        "  LEFT JOIN vinted_items v ON v.purchase_expense_id = e.id"
        " WHERE e.expense_date >= ? AND e.expense_date <= ?",
        (VINTED, *window),
    ).fetchone()
    sold = db.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(i.amount_cents), 0) AS cents,"
        "       COALESCE(SUM(e.amount_cents), 0) AS cost"
        "  FROM vinted_items v"
        "  JOIN incomes i ON i.id = v.sale_income_id"
        "  LEFT JOIN expenses e ON e.id = v.purchase_expense_id"
        " WHERE i.income_date >= ? AND i.income_date <= ?",
        window,
    ).fetchone()
    return {
        "sales_cents": sales["cents"],
        "sales_count": sales["count"],
        "expense_cents": spent["cents"],
        "expense_count": spent["count"],
        "purchase_count": spent["purchases"],
        "extra_count": spent["count"] - spent["purchases"],
        "purchase_cents": spent["purchase_cents"],
        "extra_cents": spent["cents"] - spent["purchase_cents"],
        "balance_cents": sales["cents"] - spent["cents"],
        "sold_count": sold["count"],
        "sold_cents": sold["cents"],
        "sold_cost_cents": sold["cost"],
        "gain_cents": sold["cents"] - sold["cost"],
    }


@router.get("/summary", response_model=VintedSummaryOut)
def vinted_summary(
    month: str = Query(..., description="YYYY-MM"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """The month of the section: sales, Vinted expenses (purchases and
    extras) and their difference; the items sold in the month with what
    they cost; the sales of the calendar year, for the DAC7 thresholds."""
    start, end = month_bounds(month)
    year = start.year
    yearly = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS cents, COUNT(*) AS count FROM incomes"
        " WHERE category = ? AND income_date >= ? AND income_date <= ?",
        (VINTED, f"{year:04d}-01-01", f"{year:04d}-12-31"),
    ).fetchone()
    return {
        "month": month,
        **_section_totals(db, start, end),
        "year": year,
        "year_sales_count": yearly["count"],
        "year_sales_cents": yearly["cents"],
    }


@router.get("/summary/period", response_model=VintedPeriodOut)
def vinted_period(
    date_from: date = Query(..., alias="from", description="First day, YYYY-MM-DD"),
    date_to: date = Query(..., alias="to", description="Last day, YYYY-MM-DD, included"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """The section over any period ("Esplora", 0.9.0): the figures of the
    month summary, between two dates."""
    start, end = resolve_range(None, date_from, date_to)
    return {"start": start, "end": end, **_section_totals(db, start, end)}


@router.get("/summary/trend", response_model=list[MonthTotals])
def vinted_trend(
    month: str = Query(..., description="Last month of the window, YYYY-MM"),
    months: int = Query(6, ge=1, le=24, description="How many months, ending with `month`"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Vinted sales (as ``income_*``) and Vinted expenses (as ``expense_*``)
    of each month in the window, oldest first, with zeros where nothing was
    recorded: the same shape as GET /summary/trend."""
    start, end, totals = trend_skeleton(month, months)
    window = (start.isoformat(), end.isoformat())
    for prefix, query in (
        (
            "income",
            "SELECT substr(income_date, 1, 7) AS month, SUM(amount_cents) AS cents,"
            " COUNT(*) AS count FROM incomes"
            " WHERE category = ? AND income_date >= ? AND income_date <= ? GROUP BY 1",
        ),
        (
            "expense",
            "SELECT substr(e.expense_date, 1, 7) AS month, SUM(e.amount_cents) AS cents,"
            " COUNT(*) AS count FROM expenses e"
            " JOIN categories c ON c.id = e.category_id AND c.system_key = ?"
            " WHERE e.expense_date >= ? AND e.expense_date <= ? GROUP BY 1",
        ),
    ):
        for row in db.execute(query, (VINTED, *window)).fetchall():
            totals[row["month"]][f"{prefix}_cents"] = row["cents"]
            totals[row["month"]][f"{prefix}_count"] = row["count"]
    for item in totals.values():
        item["balance_cents"] = item["income_cents"] - item["expense_cents"]
    return list(totals.values())
