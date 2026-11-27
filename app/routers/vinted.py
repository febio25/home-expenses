"""Vinted section (0.8.0): items bought to resell, or sold from home.

An item has a title, a note, a status and a photo. Its money is an expense
in the Vinted category (the purchase; none for things already at home) and
an income in the category "vinted" (the sale): the item only points at them.
So the household totals, the summary and the CSV exports count Vinted with
no extra code, and an amount corrected in "Movimenti" is the item's amount
too. Deleting that expense or income leaves the item without it (ON DELETE
SET NULL); deleting the item deletes both.

From 0.10.0 an item can wait before it goes on Vinted: ``listed_on`` is the
day it was published there, NULL until then (status "unlisted", "Da
pubblicare" in the app). An item also has the details and the text of its
ad, written with Claude by hand (app/vinted_listing.py), and the history of
its asking price on Vinted.

0.17.0: the photos and the summary of the section have modules of their
own (vinted_photos.py, vinted_summary.py), with the same address prefix;
the items, their purchase and sale, and their ad stay here.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from .. import dates, vinted_listing, vinted_markdown
from ..dates import check_expense_date
from ..db import get_db, utc_now
from ..schemas import ExpenseCreate, ExpenseOut, IncomeCreate, IncomeOut
from ..security import current_user
from ..validation import clean_note, require_amount
from ..vinted_schemas import (
    VINTED_CONDITIONS,
    VINTED_KINDS,
    VINTED_TEXT_LIMITS,
    VintedItemCreate,
    VintedItemOut,
    VintedItemUpdate,
    VintedListingIn,
    VintedListingOptionsOut,
    VintedListingParseIn,
    VintedListingParseOut,
    VintedListingRequestOut,
    VintedMarkdownIn,
    VintedPurchaseIn,
    VintedSaleIn,
)
from .expenses import EXPENSE_SELECT, insert_expense
from .incomes import INCOME_SELECT, income_out, insert_income
from .merchants import prune_merchant

router = APIRouter(prefix="/vinted", tags=["vinted"])

# categories.system_key of the section's expense category, and the code of
# its income category (INCOME_CATEGORIES in schemas.py).
VINTED = "vinted"
# "Vendite": a sale recorded there before 0.8.0 moves to "vinted" once
# linked to an item.
SALE = "sale"
UNLINKED_LIMIT = 60

ITEM_SELECT = """
SELECT v.id, v.title, v.note, v.listed_on, v.is_withdrawn, v.created_at, v.updated_at,
       v.kind, v.brand, v.size, v.condition, v.color_material, v.measurements,
       v.book_author, v.book_publisher_year, v.defects, v.similar_prices,
       v.listing_title, v.listing_description, v.price_cents, v.min_price_cents,
       v.markdown_kind, v.markdown_amount, v.markdown_days, v.markdown_source,
       v.markdown_skipped_on, v.markdown_settled_on,
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


# The day that places an item in time, for sorting: sale, else publication,
# else purchase, else the day it was added (UTC: off by one at most near midnight).
ITEM_DATE = "COALESCE(i.income_date, v.listed_on, e.expense_date, substr(v.created_at, 1, 10))"


# Detail columns of vinted_items: one line of text each.
DETAIL_TEXT_FIELDS = [
    "brand", "size", "color_material", "measurements", "book_author", "book_publisher_year",
    "defects", "similar_prices",
]


def item_out(row: sqlite3.Row, price_changes: list[dict] | None = None) -> dict:
    """An item as the API returns it. ``price_changes``: its rows of
    vinted_price_changes, oldest first (none if not given)."""
    price_changes = price_changes or []
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
    elif row["is_withdrawn"]:
        status = "withdrawn"
    else:
        status = "listed" if row["listed_on"] is not None else "unlisted"
    # Things already at home cost nothing: their gain is the whole price.
    gain = sale["amount_cents"] - (purchase["amount_cents"] if purchase else 0) if sale else None
    item = {
        "id": row["id"],
        "title": row["title"],
        "note": row["note"],
        "status": status,
        "listed_on": row["listed_on"],
        "photo": row["photo"],
        "purchase": purchase,
        "sale": sale,
        "gain_cents": gain,
        "details": {
            "kind": row["kind"],
            "kind_name": VINTED_KINDS.get(row["kind"]) if row["kind"] else None,
            "condition": row["condition"],
            "condition_name": VINTED_CONDITIONS.get(row["condition"]) if row["condition"] else None,
            **{field: row[field] for field in DETAIL_TEXT_FIELDS},
        },
        "listing": {
            "title": row["listing_title"],
            # 0.11.0: without a title of its own, the ad uses the item's name.
            "effective_title": row["listing_title"] or row["title"],
            "description": row["listing_description"],
            "price_cents": row["price_cents"],
            "min_price_cents": row["min_price_cents"],
            "start_price_cents": price_changes[0]["price_cents"] if price_changes else None,
            "price_changes": price_changes,
        },
        "created_by_name": row["created_by_name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    item["markdown"] = vinted_markdown.state_of(item, row, dates.today())  # 0.19.0
    return item


def price_changes_of(db: sqlite3.Connection, item_id: int | None = None) -> dict[int, list[dict]]:
    """Price history by item id (of one item, or of all), oldest first."""
    query = "SELECT item_id, price_cents, changed_on FROM vinted_price_changes"
    params: tuple = ()
    if item_id is not None:
        query += " WHERE item_id = ?"
        params = (item_id,)
    history: dict[int, list[dict]] = {}
    for row in db.execute(f"{query} ORDER BY changed_on, id", params):
        history.setdefault(row["item_id"], []).append(
            {"price_cents": row["price_cents"], "changed_on": row["changed_on"]}
        )
    return history


def items_out(db: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[dict]:
    history = price_changes_of(db)
    return [item_out(row, history.get(row["id"])) for row in rows]


def fetch_item(db: sqlite3.Connection, item_id: int) -> dict:
    row = db.execute(f"{ITEM_SELECT} WHERE v.id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Articolo non trovato.")
    return item_out(row, price_changes_of(db, item_id).get(item_id))


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


def check_listed_on(listed_on: date, purchase_date: str | None, sale_date: str | None) -> None:
    """The day an item went on Vinted: a real day, not in the future, not
    before it was bought and not after it was sold (422)."""
    check_expense_date(listed_on)
    if purchase_date is not None and listed_on < date.fromisoformat(purchase_date):
        raise HTTPException(
            status_code=422, detail="La data di pubblicazione non può essere prima dell'acquisto."
        )
    if sale_date is not None and listed_on > date.fromisoformat(sale_date):
        raise HTTPException(
            status_code=422, detail="La data di pubblicazione non può essere dopo la vendita."
        )


def _clean_line(text: str | None) -> str | None:
    if text is None:
        return None
    return " ".join(text.split()) or None


def _clean_text(text: str | None) -> str | None:
    """Several lines (the description of an ad): spaces at the end of each
    line and runs of blank lines removed."""
    if text is None:
        return None
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    cleaned = "\n".join(lines).strip()
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    return cleaned or None


def _optional_amount(text: str | None) -> int | None:
    if text is None or not text.strip():
        return None
    return require_amount(text)


def listing_changes(body: VintedListingIn, sent: set[str]) -> dict[str, object]:
    """Columns to write for the details and listing fields present in the
    body (all of them when creating): null or blank clears a field."""
    changes: dict[str, object] = {}
    if "kind" in sent:
        changes["kind"] = body.kind
    if "condition" in sent:
        changes["condition"] = body.condition
    for field in DETAIL_TEXT_FIELDS:
        if field in sent:
            changes[field] = _clean_line(getattr(body, field))
    if "listing_title" in sent:
        changes["listing_title"] = _clean_line(body.listing_title)
    if "listing_description" in sent:
        changes["listing_description"] = _clean_text(body.listing_description)
    if "price" in sent:
        changes["price_cents"] = _optional_amount(body.price)
    if "min_price" in sent:
        changes["min_price_cents"] = _optional_amount(body.min_price)
    return changes


def markdown_changes(body: VintedMarkdownIn) -> dict[str, object]:
    """The columns for a markdown plan sent in a PATCH (0.19.0)."""
    if body.plan == "base":
        return vinted_markdown.plan_columns(None, body.source)
    if body.plan == "none":
        return vinted_markdown.plan_columns({"kind": "none"}, body.source)
    if body.days is None or not body.amount:
        raise HTTPException(status_code=422, detail="Indica di quanto ribassare e ogni quanti giorni.")
    unit = "%" if body.plan == "pct" else "€"
    plan = vinted_markdown.parse_plan(f"{body.amount.strip()} {unit} ogni {body.days} giorni")
    if plan is None:
        raise HTTPException(
            status_code=422,
            detail="Ribasso non valido: da 1% a 50%, oppure da 0,50 € in su, ogni 1–90 giorni.",
        )
    return vinted_markdown.plan_columns(plan, body.source)


def check_prices(price: int | None, minimum: int | None) -> None:
    if price is not None and minimum is not None and minimum > price:
        raise HTTPException(
            status_code=422, detail="Il prezzo minimo non può superare il prezzo dell'annuncio."
        )


def sync_price_history(
    db: sqlite3.Connection,
    item_id: int,
    before: tuple[str | None, int | None],
    after: tuple[str | None, int | None],
    on_sale: bool,
) -> None:
    """Keep vinted_price_changes in step with (listed_on, price_cents),
    before and after a change. The first row is the price on the day the
    item was published, and stays; then a row for each day the price
    changed while it was on sale (a second change on the same day corrects
    that day's row). An item taken back to "Da pubblicare" was never on
    Vinted: no history."""
    old_listed, old_price = before
    new_listed, new_price = after
    if new_listed is None:
        db.execute("DELETE FROM vinted_price_changes WHERE item_id = ?", (item_id,))
        return
    now = utc_now()

    def add(price: int, day: str) -> None:
        db.execute(
            "INSERT INTO vinted_price_changes (item_id, price_cents, changed_on, created_at)"
            " VALUES (?, ?, ?, ?)",
            (item_id, price, day, now),
        )

    if old_listed is None:  # published now
        db.execute("DELETE FROM vinted_price_changes WHERE item_id = ?", (item_id,))
        if new_price is not None:
            add(new_price, new_listed)
        return
    rows = db.execute(
        "SELECT id, price_cents, changed_on FROM vinted_price_changes WHERE item_id = ?"
        " ORDER BY changed_on, id",
        (item_id,),
    ).fetchall()
    if new_listed != old_listed and rows:
        db.execute(
            "UPDATE vinted_price_changes SET changed_on = ? WHERE id = ?", (new_listed, rows[0]["id"])
        )
    if new_price is None or new_price == old_price or not on_sale:
        return
    today = max(dates.today().isoformat(), new_listed)
    last = rows[-1] if rows else None
    if last is None:
        add(new_price, today)
    elif last["price_cents"] == new_price:
        return
    elif last["changed_on"] == today and len(rows) > 1:
        db.execute("UPDATE vinted_price_changes SET price_cents = ? WHERE id = ?", (new_price, last["id"]))
    else:
        add(new_price, today)


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
    status: str | None = Query(None, pattern="^(unlisted|listed|sold|withdrawn)$"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """All items, newest first: sold ones by sale date, the others by the
    day they went on Vinted, items not on Vinted yet by purchase date (or
    the day they were added). With ``status``, only the items in it."""
    rows = db.execute(f"{ITEM_SELECT} ORDER BY {ITEM_DATE} DESC, v.id DESC").fetchall()
    items = items_out(db, rows)
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
    expense in the Vinted category, or one already recorded there. Without
    ``listed_on`` the item is not on Vinted yet ("Da pubblicare").

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
        check_listed_on(body.listed_on, purchase_date, None)
    listing = listing_changes(body, set(VintedListingIn.model_fields))
    check_prices(listing["price_cents"], listing["min_price_cents"])
    listed_on = body.listed_on.isoformat() if body.listed_on is not None else None

    now = utc_now()
    columns = {
        "client_uuid": body.client_uuid,
        "title": title,
        "note": clean_note(body.note),
        "listed_on": listed_on,
        "purchase_expense_id": expense_id,
        "created_by_user_id": user["id"],
        "created_at": now,
        "updated_at": now,
        **listing,
    }
    try:
        cursor = db.execute(
            f"INSERT INTO vinted_items ({', '.join(columns)})"
            f" VALUES ({', '.join('?' for _ in columns)})",
            tuple(columns.values()),
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
    sync_price_history(db, cursor.lastrowid, (None, None), (listed_on, listing["price_cents"]), True)
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
    """Title, note, day of publication on Vinted (null: not on Vinted yet),
    withdrawn, the details and the listing (text and asking price; a new
    price of an item on sale goes into its price history). The prices and
    dates of purchase and sale belong to the expense and the income: change
    them there (PATCH /expenses/{id}, /incomes/{id})."""
    item = _item_row(db, item_id)
    sent = body.model_fields_set
    changes: dict[str, object] = {}
    if "title" in sent:
        changes["title"] = _clean_title(body.title)
    if "note" in sent:
        changes["note"] = clean_note(body.note)
    if "listed_on" in sent:
        if body.listed_on is not None:
            linked = db.execute(
                "SELECT e.expense_date, i.income_date FROM vinted_items v"
                "  LEFT JOIN expenses e ON e.id = v.purchase_expense_id"
                "  LEFT JOIN incomes i ON i.id = v.sale_income_id"
                " WHERE v.id = ?",
                (item_id,),
            ).fetchone()
            check_listed_on(body.listed_on, linked["expense_date"], linked["income_date"])
        changes["listed_on"] = body.listed_on.isoformat() if body.listed_on is not None else None
    if "is_withdrawn" in sent:
        if body.is_withdrawn is None:
            raise HTTPException(status_code=422, detail="Indica se l'articolo è ritirato.")
        if body.is_withdrawn and item["sale_income_id"] is not None:
            raise HTTPException(
                status_code=409,
                detail="Un articolo venduto non si può ritirare: annulla prima la vendita.",
            )
        changes["is_withdrawn"] = int(body.is_withdrawn)
    changes.update(listing_changes(body, sent))
    if "markdown" in sent and body.markdown is not None:
        changes.update(markdown_changes(body.markdown))
    check_prices(
        changes.get("price_cents", item["price_cents"]),
        changes.get("min_price_cents", item["min_price_cents"]),
    )
    if changes:
        changes["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in changes)
        db.execute(
            f"UPDATE vinted_items SET {assignments} WHERE id = ?", (*changes.values(), item_id)
        )
        on_sale = item["sale_income_id"] is None and not changes.get("is_withdrawn", item["is_withdrawn"])
        sync_price_history(
            db,
            item_id,
            (item["listed_on"], item["price_cents"]),
            (changes.get("listed_on", item["listed_on"]), changes.get("price_cents", item["price_cents"])),
            on_sale,
        )
        db.commit()
    return fetch_item(db, item_id)


@router.post("/items/{item_id}/markdown/skip", response_model=VintedItemOut)
def skip_markdown(
    item_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """«Salta» (0.19.0): the step due is put off by a round, counted from
    today; the price does not change."""
    item = fetch_item(db, item_id)
    if item["markdown"]["state"] not in ("due", "review"):
        raise HTTPException(status_code=409, detail="Non c'è un ribasso da saltare per questo articolo.")
    db.execute(
        "UPDATE vinted_items SET markdown_skipped_on = ?, updated_at = ? WHERE id = ?",
        (dates.today().isoformat(), utc_now(), item_id),
    )
    db.commit()
    return fetch_item(db, item_id)


@router.post("/items/{item_id}/markdown/settle", response_model=VintedItemOut)
def settle_markdown(
    item_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """«Lascia così» (0.19.0): at the minimum, it stays on sale at that
    price and asks nothing more, until the price changes again."""
    item = fetch_item(db, item_id)
    if item["markdown"]["state"] not in ("at_minimum", "review"):
        raise HTTPException(status_code=409, detail="L'articolo non è al minimo.")
    db.execute(
        "UPDATE vinted_items SET markdown_settled_on = ?, updated_at = ? WHERE id = ?",
        (dates.today().isoformat(), utc_now(), item_id),
    )
    db.commit()
    return fetch_item(db, item_id)


# --- listings written with Claude ---------------------------------------------------


@router.get("/listing/options", response_model=VintedListingOptionsOut)
def listing_options(user: sqlite3.Row = Depends(current_user)):
    """The kinds of item (with the details asked for each), the conditions
    with the words of the Vinted app, and the names of the detail fields."""
    return vinted_listing.options()


@router.get("/items/{item_id}/listing-request", response_model=VintedListingRequestOut)
def listing_request(
    item_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """The message to share with Claude: the item's data, the rules and the
    answer format that POST /vinted/listing/parse reads back. For an item
    already on sale it asks for an updated price."""
    item = fetch_item(db, item_id)
    return {"text": vinted_listing.build_request(item, dates.today()), "has_photo": item["photo"] is not None}


@router.post("/listing/parse", response_model=VintedListingParseOut)
def listing_parse(body: VintedListingParseIn, user: sqlite3.Row = Depends(current_user)):
    """Read Claude's answer: title, description, price, minimum and the
    things to check. Saves nothing; never fails on an answer out of format
    (then the whole text is the description). The request itself, pasted
    by mistake (it is still on the clipboard after «Condividi con Claude»),
    is refused: its example would fill the form with someone else's ad."""
    if vinted_listing.is_request(body.text):
        raise HTTPException(
            status_code=422,
            detail="Questa è la richiesta per Claude, non la sua risposta: copia la risposta di Claude e riprova.",
        )
    parsed = vinted_listing.parse_answer(body.text)
    if parsed["title"]:
        parsed["title"] = parsed["title"][: VINTED_TEXT_LIMITS["listing_title"]]
    if parsed["description"]:
        parsed["description"] = parsed["description"][: VINTED_TEXT_LIMITS["listing_description"]]
    return parsed


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
    item is back where it was: on sale, or not on Vinted yet."""
    item = _item_row(db, item_id)
    if item["sale_income_id"] is None:
        raise HTTPException(status_code=409, detail="L'articolo non risulta venduto.")
    db.execute("DELETE FROM incomes WHERE id = ?", (item["sale_income_id"],))
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
