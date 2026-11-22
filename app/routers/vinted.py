"""Vinted section (0.8.0): items bought to resell, or sold from home.

An item has a title, a note, a status and a photo. Its money is an expense
in the Vinted category (the purchase; none for things already at home) and
an income in the category "vinted" (the sale): the item only points at them.
So the household totals, the summary and the CSV exports count Vinted with
no extra code, and an amount corrected in "Movimenti" is the item's amount
too. Deleting that expense or income leaves the item without it (ON DELETE
SET NULL); deleting the item deletes both.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from .. import dates
from ..dates import check_expense_date, month_bounds, resolve_range
from ..db import get_db, utc_now
from ..schemas import (
    ExpenseCreate,
    ExpenseOut,
    IncomeCreate,
    IncomeOut,
    MonthTotals,
    VintedItemCreate,
    VintedItemOut,
    VintedItemUpdate,
    VintedPeriodOut,
    VintedPhotoIn,
    VintedPurchaseIn,
    VintedSaleIn,
    VintedSummaryOut,
)
from ..security import current_user
from .expenses import EXPENSE_SELECT, _clean_note, insert_expense
from .incomes import INCOME_SELECT, income_out, insert_income
from .merchants import prune_merchant
from .summary import trend_skeleton

router = APIRouter(prefix="/vinted", tags=["vinted"])

# categories.system_key of the section's expense category, and the code of
# its income category (INCOME_CATEGORIES in schemas.py).
VINTED = "vinted"
# "Vendite": a sale recorded there before 0.8.0 moves to "vinted" once
# linked to an item.
SALE = "sale"
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_THUMB_BYTES = 300 * 1024
JPEG_MAGIC = b"\xff\xd8\xff"
UNLINKED_LIMIT = 60

ITEM_SELECT = """
SELECT v.id, v.title, v.note, v.listed_on, v.is_withdrawn, v.created_at, v.updated_at,
       author.display_name AS created_by_name,
       p.token AS photo,
       e.id AS e_id, e.amount_cents AS e_amount, e.expense_date AS e_date,
       m.name AS e_merchant, e.paid_by_user_id AS e_payer_id, payer.display_name AS e_payer,
       e.payment_method AS e_method,
       i.id AS i_id, i.amount_cents AS i_amount, i.income_date AS i_date,
       i.received_by_user_id AS i_receiver_id, receiver.display_name AS i_receiver
  FROM vinted_items v
  JOIN users author ON author.id = v.created_by_user_id
  LEFT JOIN vinted_photos p ON p.item_id = v.id
  LEFT JOIN expenses e ON e.id = v.purchase_expense_id
  LEFT JOIN merchants m ON m.id = e.merchant_id
  LEFT JOIN users payer ON payer.id = e.paid_by_user_id
  LEFT JOIN incomes i ON i.id = v.sale_income_id
  LEFT JOIN users receiver ON receiver.id = i.received_by_user_id
"""


def item_out(row: sqlite3.Row) -> dict:
    purchase = None
    if row["e_id"] is not None:
        purchase = {
            "expense_id": row["e_id"],
            "amount_cents": row["e_amount"],
            "expense_date": row["e_date"],
            "merchant_name": row["e_merchant"],
            "paid_by_user_id": row["e_payer_id"],
            "paid_by_name": row["e_payer"],
            "payment_method": row["e_method"],
        }
    sale = None
    if row["i_id"] is not None:
        sale = {
            "income_id": row["i_id"],
            "amount_cents": row["i_amount"],
            "income_date": row["i_date"],
            "received_by_user_id": row["i_receiver_id"],
            "received_by_name": row["i_receiver"],
        }
    if sale:
        status = "sold"
    else:
        status = "withdrawn" if row["is_withdrawn"] else "listed"
    # Things already at home cost nothing: their gain is the whole price.
    gain = sale["amount_cents"] - (purchase["amount_cents"] if purchase else 0) if sale else None
    return {
        "id": row["id"],
        "title": row["title"],
        "note": row["note"],
        "status": status,
        "listed_on": row["listed_on"],
        "photo": row["photo"],
        "purchase": purchase,
        "sale": sale,
        "gain_cents": gain,
        "created_by_name": row["created_by_name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def fetch_item(db: sqlite3.Connection, item_id: int) -> dict:
    row = db.execute(f"{ITEM_SELECT} WHERE v.id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Articolo non trovato.")
    return item_out(row)


def _item_row(db: sqlite3.Connection, item_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM vinted_items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Articolo non trovato.")
    return row


def vinted_category_id(db: sqlite3.Connection) -> int:
    row = db.execute("SELECT id FROM categories WHERE system_key = ?", (VINTED,)).fetchone()
    if row is None:  # created by migration 005: only a damaged database lacks it
        raise HTTPException(status_code=500, detail="Manca la categoria Vinted.")
    return row["id"]


def _clean_title(title: str | None) -> str:
    cleaned = " ".join((title or "").split())
    if not cleaned:
        raise HTTPException(status_code=422, detail="Scrivi il titolo dell'articolo.")
    return cleaned


def _purchase(db: sqlite3.Connection, user: sqlite3.Row, body: VintedPurchaseIn) -> tuple[int, str]:
    """The expense that bought an item, without committing: (id, date)."""
    if body.expense_id is not None:
        row = db.execute(
            "SELECT e.id, e.expense_date, c.system_key, v.id AS item_id FROM expenses e"
            "  JOIN categories c ON c.id = e.category_id"
            "  LEFT JOIN vinted_items v ON v.purchase_expense_id = e.id"
            " WHERE e.id = ?",
            (body.expense_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=422, detail="Spesa non trovata.")
        if row["system_key"] != VINTED:
            raise HTTPException(
                status_code=422, detail="Si può collegare solo una spesa della categoria Vinted."
            )
        if row["item_id"] is not None:
            raise HTTPException(
                status_code=409, detail="Questa spesa è già l'acquisto di un altro articolo."
            )
        return row["id"], row["expense_date"]
    if not (body.amount or "").strip():
        raise HTTPException(status_code=422, detail="Inserisci il prezzo pagato.")
    if body.expense_date is None:
        raise HTTPException(status_code=422, detail="Inserisci la data dell'acquisto.")
    expense_id, _ = insert_expense(
        db,
        user,
        ExpenseCreate(
            amount=body.amount,
            category_id=vinted_category_id(db),
            merchant=body.merchant,
            expense_date=body.expense_date,
            paid_by_user_id=body.paid_by_user_id,
            payment_method=body.payment_method,
        ),
    )
    return expense_id, body.expense_date.isoformat()


def _sale(db: sqlite3.Connection, user: sqlite3.Row, body: VintedSaleIn) -> int:
    """The income that sold an item, without committing."""
    if body.income_id is not None:
        row = db.execute(
            "SELECT i.id, i.category, v.id AS item_id FROM incomes i"
            "  LEFT JOIN vinted_items v ON v.sale_income_id = i.id"
            " WHERE i.id = ?",
            (body.income_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=422, detail="Entrata non trovata.")
        if row["category"] not in (VINTED, SALE):
            raise HTTPException(
                status_code=422, detail="Si può collegare solo un'entrata Vinted o Vendite."
            )
        if row["item_id"] is not None:
            raise HTTPException(
                status_code=409, detail="Questa entrata è già la vendita di un altro articolo."
            )
        if row["category"] != VINTED:
            db.execute(
                "UPDATE incomes SET category = ?, updated_at = ? WHERE id = ?",
                (VINTED, utc_now(), row["id"]),
            )
        return row["id"]
    if not (body.amount or "").strip():
        raise HTTPException(status_code=422, detail="Inserisci il prezzo di vendita.")
    income_id, _ = insert_income(
        db,
        user,
        IncomeCreate(
            amount=body.amount,
            category=VINTED,
            income_date=body.income_date or dates.today(),
            received_by_user_id=body.received_by_user_id,
            client_uuid=body.client_uuid,
        ),
    )
    return income_id


# --- items -------------------------------------------------------------------


@router.get("/items", response_model=list[VintedItemOut])
def list_items(
    status: str | None = Query(None, pattern="^(listed|sold|withdrawn)$"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """All items, newest first (sold ones by sale date). With ``status``,
    only listed, sold or withdrawn ones."""
    rows = db.execute(
        f"{ITEM_SELECT} ORDER BY COALESCE(i.income_date, v.listed_on) DESC, v.id DESC"
    ).fetchall()
    items = [item_out(row) for row in rows]
    if status:
        items = [item for item in items if item["status"] == status]
    return items


@router.post("/items", response_model=VintedItemOut, status_code=201)
def create_item(
    body: VintedItemCreate,
    response: Response,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Add an item, with its purchase if it was bought to resell: a new
    expense in the Vinted category, or one already recorded there.

    Retrying with the same ``client_uuid`` returns the item already saved,
    with status 200.
    """
    if body.client_uuid:
        existing = db.execute(
            "SELECT id FROM vinted_items WHERE client_uuid = ?", (body.client_uuid,)
        ).fetchone()
        if existing is not None:
            response.status_code = 200
            return fetch_item(db, existing["id"])

    title = _clean_title(body.title)
    expense_id, purchase_date = None, None
    if body.purchase is not None:
        expense_id, purchase_date = _purchase(db, user, body.purchase)
    if body.listed_on is not None:
        listed_on = body.listed_on
    elif purchase_date is not None:
        listed_on = date.fromisoformat(purchase_date)
    else:
        listed_on = dates.today()
    check_expense_date(listed_on)

    now = utc_now()
    try:
        cursor = db.execute(
            "INSERT INTO vinted_items (client_uuid, title, note, listed_on, purchase_expense_id,"
            " created_by_user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                body.client_uuid,
                title,
                _clean_note(body.note),
                listed_on.isoformat(),
                expense_id,
                user["id"],
                now,
                now,
            ),
        )
    except sqlite3.IntegrityError:
        # Two identical retries raced: the other one won (and stored the
        # purchase); drop this attempt, expense included.
        db.rollback()
        existing = db.execute(
            "SELECT id FROM vinted_items WHERE client_uuid = ?", (body.client_uuid,)
        ).fetchone()
        if existing is None:
            raise
        response.status_code = 200
        return fetch_item(db, existing["id"])
    db.commit()
    return fetch_item(db, cursor.lastrowid)


@router.get("/items/{item_id}", response_model=VintedItemOut)
def get_item(
    item_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return fetch_item(db, item_id)


@router.patch("/items/{item_id}", response_model=VintedItemOut)
def update_item(
    item_id: int,
    body: VintedItemUpdate,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Title, note, withdrawn. Prices and dates belong to the expense and
    the income: change them there (PATCH /expenses/{id}, /incomes/{id})."""
    item = _item_row(db, item_id)
    sent = body.model_fields_set
    changes: dict[str, object] = {}
    if "title" in sent:
        changes["title"] = _clean_title(body.title)
    if "note" in sent:
        changes["note"] = _clean_note(body.note)
    if "is_withdrawn" in sent:
        if body.is_withdrawn is None:
            raise HTTPException(status_code=422, detail="Indica se l'articolo è ritirato.")
        if body.is_withdrawn and item["sale_income_id"] is not None:
            raise HTTPException(
                status_code=409,
                detail="Un articolo venduto non si può ritirare: annulla prima la vendita.",
            )
        changes["is_withdrawn"] = int(body.is_withdrawn)
    if changes:
        changes["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in changes)
        db.execute(
            f"UPDATE vinted_items SET {assignments} WHERE id = ?", (*changes.values(), item_id)
        )
        db.commit()
    return fetch_item(db, item_id)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Delete the item, its photo, and the expense and income linked to it."""
    item = _item_row(db, item_id)
    db.execute("DELETE FROM vinted_items WHERE id = ?", (item_id,))  # the photo goes with it
    if item["purchase_expense_id"] is not None:
        expense = db.execute(
            "SELECT merchant_id FROM expenses WHERE id = ?", (item["purchase_expense_id"],)
        ).fetchone()
        db.execute("DELETE FROM expenses WHERE id = ?", (item["purchase_expense_id"],))
        if expense is not None:
            prune_merchant(db, expense["merchant_id"])
    if item["sale_income_id"] is not None:
        db.execute("DELETE FROM incomes WHERE id = ?", (item["sale_income_id"],))
    db.commit()


@router.post("/items/{item_id}/purchase", response_model=VintedItemOut)
def add_purchase(
    item_id: int,
    body: VintedPurchaseIn,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Give an item without a purchase its expense (new, or already recorded)."""
    item = _item_row(db, item_id)
    if item["purchase_expense_id"] is not None:
        raise HTTPException(status_code=409, detail="L'articolo ha già un acquisto.")
    expense_id, _ = _purchase(db, user, body)
    db.execute(
        "UPDATE vinted_items SET purchase_expense_id = ?, updated_at = ? WHERE id = ?",
        (expense_id, utc_now(), item_id),
    )
    db.commit()
    return fetch_item(db, item_id)


@router.post("/items/{item_id}/sale", response_model=VintedItemOut)
def record_sale(
    item_id: int,
    body: VintedSaleIn,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Mark an item as sold: a new income in the category "vinted", or one
    already recorded (a "Vendite" one moves to "vinted"). A withdrawn item
    is back in the lists as sold. Retrying with the same ``client_uuid``
    returns the item as it is."""
    item = _item_row(db, item_id)
    if item["sale_income_id"] is not None:
        if body.client_uuid:
            linked = db.execute(
                "SELECT client_uuid FROM incomes WHERE id = ?", (item["sale_income_id"],)
            ).fetchone()
            if linked is not None and linked["client_uuid"] == body.client_uuid:
                return fetch_item(db, item_id)
        raise HTTPException(status_code=409, detail="L'articolo è già venduto.")
    income_id = _sale(db, user, body)
    db.execute(
        "UPDATE vinted_items SET sale_income_id = ?, is_withdrawn = 0, updated_at = ? WHERE id = ?",
        (income_id, utc_now(), item_id),
    )
    db.commit()
    return fetch_item(db, item_id)


@router.delete("/items/{item_id}/sale", status_code=204)
def cancel_sale(
    item_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """A return, or a sale marked by mistake: the income is deleted and the
    item is on sale again."""
    item = _item_row(db, item_id)
    if item["sale_income_id"] is None:
        raise HTTPException(status_code=409, detail="L'articolo non risulta venduto.")
    db.execute("DELETE FROM incomes WHERE id = ?", (item["sale_income_id"],))
    db.execute("UPDATE vinted_items SET updated_at = ? WHERE id = ?", (utc_now(), item_id))
    db.commit()


# --- photos --------------------------------------------------------------------


def _decode_jpeg(text: str, limit: int, what: str) -> bytes:
    try:
        data = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"{what} non valida.") from error
    if not data.startswith(JPEG_MAGIC):
        raise HTTPException(status_code=422, detail=f"{what}: serve un'immagine JPEG.")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"{what} troppo grande.")
    return data


@router.put("/items/{item_id}/photo", response_model=VintedItemOut)
def put_photo(
    item_id: int,
    body: VintedPhotoIn,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Set or replace the photo. The client sends it already resized (the
    app: about 1200 px and a 160 px thumbnail, JPEG, no location data)."""
    _item_row(db, item_id)
    image = _decode_jpeg(body.image, MAX_IMAGE_BYTES, "Foto")
    thumb = _decode_jpeg(body.thumb, MAX_THUMB_BYTES, "Miniatura")
    token = hashlib.sha256(image).hexdigest()[:16]
    now = utc_now()
    db.execute(
        "INSERT INTO vinted_photos (item_id, token, created_at, image, thumb) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(item_id) DO UPDATE SET token = excluded.token,"
        " created_at = excluded.created_at, image = excluded.image, thumb = excluded.thumb",
        (item_id, token, now, image, thumb),
    )
    db.execute("UPDATE vinted_items SET updated_at = ? WHERE id = ?", (now, item_id))
    db.commit()
    return fetch_item(db, item_id)


def _photo(db: sqlite3.Connection, item_id: int, column: str, version: str | None) -> Response:
    row = db.execute(
        f"SELECT token, {column} AS data FROM vinted_photos WHERE item_id = ?", (item_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Foto non trovata.")
    # The app asks with ?v=<token>: that address never changes content, so the
    # phone keeps it. Without (or with an old) token, always ask again.
    cache = "private, max-age=31536000, immutable" if version == row["token"] else "private, no-cache"
    return Response(
        content=row["data"],
        media_type="image/jpeg",
        headers={"Cache-Control": cache, "ETag": f'"{row["token"]}-{column}"'},
    )


@router.get(
    "/items/{item_id}/photo",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}},
)
def get_photo(
    item_id: int,
    v: str | None = Query(None, description="Photo token from the item: makes the image cacheable"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return _photo(db, item_id, "image", v)


@router.get(
    "/items/{item_id}/photo/thumb",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}},
)
def get_thumb(
    item_id: int,
    v: str | None = Query(None, description="Photo token from the item: makes the image cacheable"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return _photo(db, item_id, "thumb", v)


@router.delete("/items/{item_id}/photo", status_code=204)
def delete_photo(
    item_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _item_row(db, item_id)
    db.execute("DELETE FROM vinted_photos WHERE item_id = ?", (item_id,))
    db.execute("UPDATE vinted_items SET updated_at = ? WHERE id = ?", (utc_now(), item_id))
    db.commit()


# --- what can still be linked ------------------------------------------------------


@router.get("/unlinked-expenses", response_model=list[ExpenseOut])
def unlinked_expenses(
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Expenses of the Vinted category not linked to an item, newest first:
    purchases recorded from "Nuova spesa", to attach to an item."""
    rows = db.execute(
        f"{EXPENSE_SELECT} WHERE c.system_key = ? AND v.id IS NULL"
        " ORDER BY e.expense_date DESC, e.id DESC LIMIT ?",
        (VINTED, UNLINKED_LIMIT),
    ).fetchall()
    return [dict(row) for row in rows]


@router.get("/unlinked-incomes", response_model=list[IncomeOut])
def unlinked_incomes(
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Incomes in "vinted" or "Vendite" not linked to an item, newest first."""
    rows = db.execute(
        f"{INCOME_SELECT} WHERE i.category IN (?, ?) AND v.id IS NULL"
        " ORDER BY i.income_date DESC, i.id DESC LIMIT ?",
        (VINTED, SALE, UNLINKED_LIMIT),
    ).fetchall()
    return [income_out(row) for row in rows]


# --- summary ---------------------------------------------------------------------


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
        "       COALESCE(SUM(v.id IS NOT NULL), 0) AS purchases"
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
