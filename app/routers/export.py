"""CSV export of expenses, of incomes and (0.8.0) of the Vinted items, in a
standard flavour and an Italian-Excel flavour. Separate files: the expense
CSV keeps exactly the columns it always had.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from collections.abc import Iterable
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from .. import dates
from ..dates import range_filter, resolve_range
from ..db import get_db
from ..export_brief import build_brief, period_text
from ..money import format_cents
from ..schemas import INCOME_CATEGORIES, ExportBriefOut
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


# A cell that starts with one of these is read by Excel as a formula:
# "-10% saldi" becomes #NOME?, "+ spedizione" an error. Tab and carriage
# return are on the list for the same reason (OWASP, "CSV Injection").
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
# Amounts the app writes itself (a Vinted gain can be "-5,00"): numbers,
# never text to protect.
EXCEL_NUMBER = re.compile(r"-?\d+(,\d+)?")


def excel_text(cell: str) -> str:
    """A cell of the Excel flavour, safe to open (0.14.0): text that Excel
    would take for a formula gets a leading apostrophe, Excel's own mark
    for "this is text", which Excel does not show in the cell. Numbers stay
    numbers. The standard flavour, the one for AI tools, is never touched."""
    if cell.startswith(FORMULA_START) and not EXCEL_NUMBER.fullmatch(cell):
        return "'" + cell
    return cell


def _render(header: list[str], records: Iterable[list[str]], excel: bool) -> str:
    """standard: comma separator, dot decimal. For AI tools and scripts.
    excel_it: semicolon separator, comma decimal, as Italian Excel expects,
    and text cells that look like formulas protected (``excel_text``)."""
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=";" if excel else ",",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",
    )
    writer.writerow(header)
    if excel:
        records = ([excel_text(cell) for cell in record] for record in records)
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


@router.get("/export/brief", response_model=ExportBriefOut)
def export_brief(
    month: str | None = Query(None, description="YYYY-MM; wins over from/to"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    db: sqlite3.Connection = Depends(get_db),
):
    """The CSV files of a period for an AI assistant, and the text to send
    with them (0.14.0): what they hold, the totals to check them against,
    the conventions of the app. The files are the standard flavour of
    GET /export.csv and GET /export/incomes.csv; a file with no rows is left
    out. Nothing is sent anywhere: the app downloads the files and copies
    the text."""
    start, end = resolve_range(month, date_from, date_to)
    window: dict[str, str] = {}
    if month:
        window["month"] = month
    else:
        if start:
            window["from"] = start.isoformat()
        if end:
            window["to"] = end.isoformat()
    where, params = range_filter(start, end, column="expense_date")
    future = dates.today().isoformat()
    spent = db.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount_cents), 0) AS cents,"
        "       COALESCE(SUM(expense_date > ?), 0) AS planned_count,"
        "       COALESCE(SUM(CASE WHEN expense_date > ? THEN amount_cents END), 0) AS planned_cents"
        f"  FROM expenses{where}",
        [future, future, *params],
    ).fetchone()
    where, params = range_filter(start, end, column="income_date")
    income = db.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount_cents), 0) AS cents,"
        "       COALESCE(SUM(CASE WHEN category = 'meal_voucher' THEN amount_cents END), 0) AS vouchers"
        f"  FROM incomes{where}",
        params,
    ).fetchone()
    vinted = db.execute("SELECT name FROM categories WHERE system_key = 'vinted'").fetchone()

    query = "&".join(f"{key}={value}" for key, value in {**window, "format": "standard"}.items())
    files = []
    expense_file = income_file = None
    if spent["count"]:
        expense_file = _filename("spese", month, start, end, False)
        files.append({"name": expense_file, "url": f"/api/v1/export.csv?{query}"})
    if income["count"]:
        income_file = _filename("entrate", month, start, end, False)
        files.append({"name": income_file, "url": f"/api/v1/export/incomes.csv?{query}"})
    text = build_brief(
        period=period_text(month, start, end),
        expense_file=expense_file,
        expense_count=spent["count"],
        expense_cents=spent["cents"],
        planned_count=spent["planned_count"],
        planned_cents=spent["planned_cents"],
        income_file=income_file,
        income_count=income["count"],
        income_cents=income["cents"],
        voucher_cents=income["vouchers"],
        vinted_category=vinted["name"] if vinted else None,
        vinted_income_category=INCOME_CATEGORIES["vinted"],
        voucher_category=INCOME_CATEGORIES["meal_voucher"],
    )
    return {"text": text, "files": files}
