"""Monthly summary: total and per-category totals. Nothing fancier, by design."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from ..dates import month_bounds
from ..db import get_db
from ..schemas import SummaryOut
from ..security import current_user

router = APIRouter(prefix="/summary", tags=["summary"], dependencies=[Depends(current_user)])


@router.get("", response_model=SummaryOut)
def monthly_summary(
    month: str = Query(..., description="YYYY-MM"),
    db: sqlite3.Connection = Depends(get_db),
):
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
    return {
        "month": month,
        "total_cents": sum(row["total_cents"] for row in by_category),
        "expense_count": sum(row["expense_count"] for row in by_category),
        "by_category": by_category,
    }
