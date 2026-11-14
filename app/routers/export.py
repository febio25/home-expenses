"""CSV export, in a standard flavour and an Italian-Excel flavour."""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from ..dates import range_filter, resolve_range
from ..db import get_db
from ..money import format_cents
from ..security import current_user
from .expenses import EXPENSE_SELECT

router = APIRouter(tags=["export"], dependencies=[Depends(current_user)])

CSV_COLUMNS = [
    "data",
    "importo",
    "categoria",
    "esercente",
    "nota",
    "pagato_da",
    "metodo_pagamento",
    "inserito_da",
    "creato_il",
]
PAYMENT_LABELS = {"card": "Carta", "cash": "Contanti", "other": "Altro"}


def build_csv(rows: list[sqlite3.Row], flavour: str) -> str:
    """Render expenses as CSV text.

    standard: comma separator, dot decimal. For AI tools and scripts.
    excel_it: semicolon separator, comma decimal, as Italian Excel expects.
    """
    excel = flavour == "excel_it"
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=";" if excel else ",",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",
    )
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow(
            [
                row["expense_date"],
                format_cents(row["amount_cents"], "," if excel else "."),
                row["category_name"],
                row["merchant_name"] or "",
                row["note"] or "",
                row["paid_by_name"],
                PAYMENT_LABELS[row["payment_method"]],
                row["created_by_name"],
                row["created_at"],
            ]
        )
    return buffer.getvalue()


def _filename(month: str | None, start: date | None, end: date | None, excel: bool) -> str:
    if month:
        label = month
    elif start or end:
        label = f"{start.isoformat() if start else 'inizio'}_{end.isoformat() if end else 'oggi'}"
    else:
        label = "tutte"
    return f"spese_{label}{'_excel' if excel else ''}.csv"


@router.get(
    "/export.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def export_csv(
    month: str | None = Query(None, description="YYYY-MM; wins over from/to"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    flavour: Literal["standard", "excel_it"] = Query("standard", alias="format"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Download the expenses in the range, oldest first."""
    start, end = resolve_range(month, date_from, date_to)
    where, params = range_filter(start, end)
    rows = db.execute(
        f"{EXPENSE_SELECT}{where} ORDER BY e.expense_date, e.id", params
    ).fetchall()
    excel = flavour == "excel_it"
    text = build_csv(rows, flavour)
    # Excel needs the UTF-8 byte order mark to read accented letters correctly;
    # the standard flavour stays BOM-free for parsers.
    payload = text.encode("utf-8-sig" if excel else "utf-8")
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_filename(month, start, end, excel)}"',
            "Cache-Control": "no-store",
        },
    )
