"""CSV export of expenses, of incomes and (0.8.0) of the Vinted items, in a
standard flavour and an Italian-Excel flavour. Separate files: the expense
CSV keeps exactly the columns it always had.
"""

from __future__ import annotations

import csv
import io
import sqlite3
from collections.abc import Iterable
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from .. import dates
from ..dates import range_filter, resolve_range
from ..db import get_db
from ..money import format_cents
from ..security import current_user
from .expenses import EXPENSE_SELECT
from .incomes import INCOME_SELECT, income_out
from .vinted import ITEM_SELECT, items_out

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
INCOME_CSV_COLUMNS = [
    "data",
    "importo",
    "categoria",
    "nota",
    "ricevuto_da",
    "inserito_da",
    "creato_il",
]
# One row per item: what it cost, what it made, how long it waited.
VINTED_CSV_COLUMNS = [
    "articolo",
    "stato",
    "data_acquisto",
    "prezzo_acquisto",
    "data_vendita",
    "prezzo_vendita",
    "guadagno",
    "giorni_in_vendita",
    "nota",
    "inserito_da",
    "creato_il",
    "data_pubblicazione",  # 0.10.0: new columns go at the end, the others never move
    "tipo",
    "marca",
    "taglia",
    "condizioni",
    "prezzo_partenza",
    "prezzo_attuale",
    "prezzo_minimo",
    "cambi_prezzo",
]
VINTED_STATUS_LABELS = {
    "unlisted": "Da pubblicare",
    "listed": "In vendita",
    "sold": "Venduto",
    "withdrawn": "Ritirato",
}
PAYMENT_LABELS = {"card": "Carta", "cash": "Contanti", "other": "Altro"}

Flavour = Literal["standard", "excel_it"]


def _render(header: list[str], records: Iterable[list[str]], excel: bool) -> str:
    """standard: comma separator, dot decimal. For AI tools and scripts.
    excel_it: semicolon separator, comma decimal, as Italian Excel expects."""
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=";" if excel else ",",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",
    )
    writer.writerow(header)
    writer.writerows(records)
    return buffer.getvalue()


def build_csv(rows: list[sqlite3.Row], flavour: str) -> str:
    """Render expenses as CSV text."""
    excel = flavour == "excel_it"
    return _render(
        CSV_COLUMNS,
        (
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
            for row in rows
        ),
        excel,
    )


def build_incomes_csv(rows: list[dict], flavour: str) -> str:
    """Render incomes (as returned by ``income_out``) as CSV text."""
    excel = flavour == "excel_it"
    return _render(
        INCOME_CSV_COLUMNS,
        (
            [
                row["income_date"],
                format_cents(row["amount_cents"], "," if excel else "."),
                row["category_name"],
                row["note"] or "",
                row["received_by_name"],
                row["created_by_name"],
                row["created_at"],
            ]
            for row in rows
        ),
        excel,
    )


def build_vinted_csv(items: list[dict], flavour: str, today: date) -> str:
    """Render Vinted items (as returned by ``item_out``) as CSV text.

    guadagno: sale minus purchase, the whole price for things already at
    home, empty until sold. giorni_in_vendita: from the day it was
    published on Vinted to the sale (or to today); empty for a withdrawn
    item and for one never published. data_pubblicazione: that day.
    prezzo_partenza: the asking price on the day it was published;
    prezzo_attuale and prezzo_minimo: as now; cambi_prezzo: how many times
    the price changed after that (empty if never published).
    """
    excel = flavour == "excel_it"

    def money(cents: int | None) -> str:
        return "" if cents is None else format_cents(cents, "," if excel else ".")

    records = []
    for item in items:
        purchase, sale = item["purchase"], item["sale"]
        details, listing = item["details"], item["listing"]
        days = ""
        if item["status"] != "withdrawn" and item["listed_on"] is not None:
            end = date.fromisoformat(sale["income_date"]) if sale else today
            days = str(max(0, (end - date.fromisoformat(item["listed_on"])).days))
        records.append([
            item["title"],
            VINTED_STATUS_LABELS[item["status"]],
            purchase["expense_date"] if purchase else "",
            money(purchase["amount_cents"]) if purchase else "",
            sale["income_date"] if sale else "",
            money(sale["amount_cents"]) if sale else "",
            money(item["gain_cents"]),
            days,
            item["note"] or "",
            item["created_by_name"],
            item["created_at"],
            str(item["listed_on"]) if item["listed_on"] is not None else "",
            details["kind_name"] or "",
            details["brand"] or "",
            details["size"] or "",
            details["condition_name"] or "",
            money(listing["start_price_cents"]),
            money(listing["price_cents"]),
            money(listing["min_price_cents"]),
            str(max(0, len(listing["price_changes"]) - 1)) if item["listed_on"] is not None else "",
        ])
    return _render(VINTED_CSV_COLUMNS, records, excel)


def _filename(
    prefix: str, month: str | None, start: date | None, end: date | None, excel: bool
) -> str:
    if month:
        label = month
    elif start or end:
        label = f"{start.isoformat() if start else 'inizio'}_{end.isoformat() if end else 'oggi'}"
    else:
        label = "tutte"
    return f"{prefix}_{label}{'_excel' if excel else ''}.csv"


def _csv_response(text: str, excel: bool, filename: str) -> Response:
    # Excel needs the UTF-8 byte order mark to read accented letters correctly;
    # the standard flavour stays BOM-free for parsers.
    payload = text.encode("utf-8-sig" if excel else "utf-8")
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/export.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def export_csv(
    month: str | None = Query(None, description="YYYY-MM; wins over from/to"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    flavour: Flavour = Query("standard", alias="format"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Download the expenses in the range, oldest first."""
    start, end = resolve_range(month, date_from, date_to)
    where, params = range_filter(start, end)
    rows = db.execute(
        f"{EXPENSE_SELECT}{where} ORDER BY e.expense_date, e.id", params
    ).fetchall()
    excel = flavour == "excel_it"
    return _csv_response(
        build_csv(rows, flavour), excel, _filename("spese", month, start, end, excel)
    )


@router.get(
    "/export/incomes.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def export_incomes_csv(
    month: str | None = Query(None, description="YYYY-MM; wins over from/to"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    flavour: Flavour = Query("standard", alias="format"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Download the incomes in the range, oldest first. Same filters and
    formats as the expense export, in a file of its own."""
    start, end = resolve_range(month, date_from, date_to)
    where, params = range_filter(start, end, column="i.income_date")
    rows = db.execute(
        f"{INCOME_SELECT}{where} ORDER BY i.income_date, i.id", params
    ).fetchall()
    excel = flavour == "excel_it"
    return _csv_response(
        build_incomes_csv([income_out(row) for row in rows], flavour),
        excel,
        _filename("entrate", month, start, end, excel),
    )


@router.get(
    "/export/vinted.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def export_vinted_csv(
    flavour: Flavour = Query("standard", alias="format"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Download every Vinted item, oldest first: purchase, sale, gain and
    days on sale. No date filter: the items are few and live for months."""
    rows = db.execute(
        f"{ITEM_SELECT} ORDER BY COALESCE(v.listed_on, e.expense_date, substr(v.created_at, 1, 10)), v.id"
    ).fetchall()
    excel = flavour == "excel_it"
    return _csv_response(
        build_vinted_csv(items_out(db, rows), flavour, dates.today()),
        excel,
        f"vinted_articoli{'_excel' if excel else ''}.csv",
    )
