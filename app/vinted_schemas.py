"""Pydantic models of the Vinted section (0.8.0, split from schemas.py in
0.17.0): items, their purchase, sale, photo and ad, and the summary."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from .schemas import PaymentMethod

# --- Vinted -------------------------------------------------------------------
# An item bought to resell, or sold from home. Its money lives in an expense
# (category Vinted) and an income (category "vinted"): the item points at them.

# unlisted (0.10.0): not on Vinted yet ("Da pubblicare"); listed: published
# there and waiting for a buyer; sold; withdrawn: kept or given away.
VintedStatus = Literal["unlisted", "listed", "sold", "withdrawn"]


class VintedPurchaseIn(BaseModel):
    """The purchase of an item: a new expense in the Vinted category, or,
    with ``expense_id``, one already recorded there (for example from
    "Nuova spesa")."""

    expense_id: int | None = Field(default=None, description="An expense of the Vinted category, not linked yet")
    amount: str | None = Field(default=None, max_length=20, description="Total paid: price, shipping, fees")
    expense_date: date | None = None
    merchant: str | None = Field(default=None, max_length=80, description="Where it was bought (none by default, 0.11.0)")
    paid_by_user_id: int | None = Field(default=None, description="Defaults to the logged-in user")
    payment_method: PaymentMethod = "card"


# 0.10.0, listings written with Claude: what an item is (decides the details
# asked for it), its condition with the words of the Vinted app in Italy, and
# the details of each kind, in the order of the request sent to Claude.
VINTED_KINDS = {"clothing": "Abbigliamento", "bag": "Borsa", "book": "Libro", "other": "Altro"}
VINTED_CONDITIONS = {
    "new_with_tags": "Nuovo con cartellino",
    "new_without_tags": "Nuovo senza cartellino",
    "very_good": "Ottime condizioni",
    "good": "Buone condizioni",
    "satisfactory": "Discrete condizioni",
}
VINTED_KIND_FIELDS = {
    "clothing": ["brand", "size", "condition", "color_material", "measurements", "defects"],
    "bag": ["brand", "condition", "color_material", "measurements", "defects"],
    "book": ["book_author", "book_publisher_year", "condition", "defects"],
    "other": ["brand", "condition", "color_material", "measurements", "defects"],
}
# Without a kind: everything but the book fields.
VINTED_ANY_KIND_FIELDS = VINTED_KIND_FIELDS["clothing"]
VINTED_DETAIL_LABELS = {
    "brand": "Marca",
    "size": "Taglia",
    "condition": "Stato",
    "color_material": "Colore e materiale",
    "measurements": "Misure",
    "book_author": "Autore",
    "book_publisher_year": "Editore e anno",
    "defects": "Difetti",
}
# Longest text accepted for each field (and for the listing).
VINTED_TEXT_LIMITS = {
    "brand": 60,
    "size": 30,
    "color_material": 80,
    "measurements": 120,
    "book_author": 100,
    "book_publisher_year": 80,
    "defects": 300,
    "similar_prices": 120,
    "listing_title": 200,
    "listing_description": 5000,
}

VintedKind = Literal["clothing", "bag", "book", "other"]
VintedCondition = Literal["new_with_tags", "new_without_tags", "very_good", "good", "satisfactory"]


class VintedListingIn(BaseModel):
    """The details of an item and its listing, all optional. In a PATCH,
    a field sent as null is cleared; a field not sent is left alone."""

    kind: VintedKind | None = None
    brand: str | None = Field(default=None, max_length=VINTED_TEXT_LIMITS["brand"])
    size: str | None = Field(default=None, max_length=VINTED_TEXT_LIMITS["size"])
    condition: VintedCondition | None = None
    color_material: str | None = Field(default=None, max_length=VINTED_TEXT_LIMITS["color_material"])
    measurements: str | None = Field(default=None, max_length=VINTED_TEXT_LIMITS["measurements"])
    book_author: str | None = Field(default=None, max_length=VINTED_TEXT_LIMITS["book_author"])
    book_publisher_year: str | None = Field(
        default=None, max_length=VINTED_TEXT_LIMITS["book_publisher_year"]
    )
    defects: str | None = Field(default=None, max_length=VINTED_TEXT_LIMITS["defects"])
    similar_prices: str | None = Field(
        default=None, max_length=VINTED_TEXT_LIMITS["similar_prices"],
        description="Prices seen on Vinted for similar items, as typed (\"20, 25, 18\")",
    )
    listing_title: str | None = Field(default=None, max_length=VINTED_TEXT_LIMITS["listing_title"])
    listing_description: str | None = Field(
        default=None, max_length=VINTED_TEXT_LIMITS["listing_description"]
    )
    price: str | None = Field(
        default=None, max_length=20,
        description="Asking price on Vinted, as typed (\"25\", \"22,50\"). On an item on sale, a"
        " new price goes into its price history",
    )
    min_price: str | None = Field(default=None, max_length=20, description="Not below this")


class VintedItemCreate(VintedListingIn):
    title: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=300)
    listed_on: date | None = Field(
        default=None,
        description="Day it was published on Vinted; missing or null: not on Vinted yet",
    )
    purchase: VintedPurchaseIn | None = Field(default=None, description="None for things already at home")
    client_uuid: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        description="Idempotency key: retrying with the same value never creates a duplicate",
    )


# --- markdowns (0.19.0) -------------------------------------------------------------

VintedMarkdownKind = Literal["pct", "eur", "none"]
VintedMarkdownState = Literal["inactive", "off", "no_minimum", "waiting", "due", "at_minimum", "review", "settled"]


class VintedMarkdownIn(BaseModel):
    """The markdown plan of an item. plan "base": the app's base plan (10%
    every 14 days); "pct" or "eur" with amount ("10" percent, "2,50" euro)
    and days; "none": never marked down."""

    plan: Literal["base", "pct", "eur", "none"]
    amount: str | None = Field(default=None, max_length=20, description='"10" (percent) or "2,50" (euro)')
    days: int | None = Field(default=None, ge=1, le=90)
    source: Literal["claude", "manual"] = Field("manual", description="Who chose it: Claude's answer or by hand")


class VintedMarkdownPlanOut(BaseModel):
    kind: VintedMarkdownKind
    amount: int | None = Field(description="Percent for pct, cents for eur, null for none")
    days: int | None
    source: Literal["base", "claude", "manual"]
    text: str = Field(description='As the app writes it: "−10% ogni 14 giorni"')


class VintedMarkdownOut(BaseModel):
    plan: VintedMarkdownPlanOut
    state: VintedMarkdownState
    since: date | None = Field(description="Day of the last change of price (or of publication)")
    due_on: date | None = Field(description="Day the next step is due (at the minimum: the end of the round)")
    next_price_cents: int | None = Field(description="Price of the next step, above the minimum only")
    steps: list[int] = Field(description="Prices of the steps to come, the minimum last")


class VintedItemUpdate(VintedListingIn):
    """Partial update. ``"note": null`` clears the note; ``"listed_on": null``
    puts the item back among the ones not on Vinted yet."""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=300)
    listed_on: date | None = Field(
        default=None,
        description="Day it was published on Vinted: not in the future, not before the"
        " purchase, not after the sale",
    )
    is_withdrawn: bool | None = Field(default=None, description="Kept or given away: no longer for sale")
    markdown: VintedMarkdownIn | None = Field(default=None, description="0.19.0: the markdown plan")


class VintedSaleIn(BaseModel):
    """The sale of an item: a new income in the category "vinted", or, with
    ``income_id``, one already recorded in "vinted" or "sale" (moved to
    "vinted")."""

    income_id: int | None = None
    amount: str | None = Field(default=None, max_length=20, description="Amount received")
    income_date: date | None = Field(default=None, description="Defaults to today")
    received_by_user_id: int | None = Field(default=None, description="Defaults to the logged-in user")
    client_uuid: str | None = Field(default=None, min_length=8, max_length=64)


class VintedPhotoIn(BaseModel):
    """JPEG images in base64, resized by the client: the photo (about
    1200 px) and its thumbnail (about 160 px)."""

    image: str = Field(max_length=4_400_000)
    thumb: str = Field(max_length=440_000)


class VintedPurchaseOut(BaseModel):
    expense_id: int
    amount_cents: int
    expense_date: date
    merchant_name: str | None
    paid_by_user_id: int
    paid_by_name: str
    payment_method: PaymentMethod


class VintedSaleOut(BaseModel):
    income_id: int
    amount_cents: int
    income_date: date
    received_by_user_id: int
    received_by_name: str


class VintedDetailsOut(BaseModel):
    kind: VintedKind | None
    kind_name: str | None
    brand: str | None
    size: str | None
    condition: VintedCondition | None
    condition_name: str | None
    color_material: str | None
    measurements: str | None
    book_author: str | None
    book_publisher_year: str | None
    defects: str | None
    similar_prices: str | None


class VintedPriceChangeOut(BaseModel):
    price_cents: int
    changed_on: date


class VintedListingOut(BaseModel):
    title: str | None = Field(description="The ad's own title, or null: then the item's name is used")
    effective_title: str = Field(description="The title to put on Vinted: the ad's own, else the item's name")
    description: str | None
    price_cents: int | None = Field(description="Asking price now")
    min_price_cents: int | None
    start_price_cents: int | None = Field(description="Price on the day it was published")
    price_changes: list[VintedPriceChangeOut] = Field(
        description="Price on Vinted over time, oldest first: the first is the day it was published"
    )


class VintedListingRequestOut(BaseModel):
    text: str = Field(description="The message for Claude: the item's data, rules and answer format")
    has_photo: bool


class VintedListingParseIn(BaseModel):
    text: str = Field(max_length=20000, description="Claude's answer, pasted")


class VintedListingParseOut(BaseModel):
    """What the app recognised in Claude's answer. Nothing is saved: the
    client shows it in the form, and saves with PATCH /vinted/items/{id}."""

    recognized: bool = Field(description="False: no TITOLO or DESCRIZIONE, the whole text is the description")
    title: str | None
    description: str | None
    price_cents: int | None
    min_price_cents: int | None
    check: str | None = Field(description="VERIFICA: what to check before publishing, shown once")
    markdown: VintedMarkdownPlanOut | None = Field(
        None, description="0.19.0: the line RIBASSO, when present and readable (source claude)"
    )
    markdown_text: str | None = Field(None, description="The line RIBASSO as written, read or not")


class VintedOptionOut(BaseModel):
    code: str
    name: str


class VintedKindOut(VintedOptionOut):
    fields: list[str]


class VintedDetailFieldOut(BaseModel):
    field: str
    name: str


class VintedListingOptionsOut(BaseModel):
    kinds: list[VintedKindOut]
    conditions: list[VintedOptionOut]
    fields: list[VintedDetailFieldOut] = Field(description="Names of the detail fields")


class VintedItemOut(BaseModel):
    id: int
    title: str
    note: str | None
    status: VintedStatus
    listed_on: date | None = Field(description="Day it was published on Vinted; null: not yet")
    photo: str | None = Field(description="Version token of the photo, null without one")
    purchase: VintedPurchaseOut | None
    sale: VintedSaleOut | None
    gain_cents: int | None = Field(
        description="Sale minus purchase (an item without purchase costs zero); null until sold"
    )
    details: VintedDetailsOut
    listing: VintedListingOut
    markdown: VintedMarkdownOut
    created_by_name: str
    created_at: str
    updated_at: str


class VintedSummaryOut(BaseModel):
    """GET /vinted/summary: one month of the section, plus its calendar year."""

    month: str
    sales_cents: int = Field(description="Incomes of the month in the category vinted")
    sales_count: int
    expense_cents: int = Field(description="Expenses of the month in the Vinted category")
    expense_count: int
    purchase_count: int = Field(description="Of those, the purchases of an item")
    extra_count: int = Field(description="Of those, the ones without an item: supplies, promotions")
    purchase_cents: int = Field(0, description="0.18.1: total of the purchases of an item")
    extra_cents: int = Field(0, description="0.18.1: total of the extras")
    balance_cents: int = Field(description="sales_cents - expense_cents; may be negative")
    sold_count: int = Field(description="Items whose sale falls in the month")
    sold_cents: int
    sold_cost_cents: int = Field(description="What those items cost (zero for things already at home)")
    gain_cents: int = Field(description="sold_cents - sold_cost_cents")
    year: int
    year_sales_count: int = Field(description="Vinted incomes of the calendar year (DAC7: 30 sales)")
    year_sales_cents: int = Field(description="Their total (DAC7: 2,000 EUR)")


class VintedPeriodOut(BaseModel):
    """GET /vinted/summary/period (0.9.0): the section over any period, for
    "Esplora": the same figures as the month summary, without the year."""

    start: date
    end: date
    sales_cents: int = Field(description="Incomes of the period in the category vinted")
    sales_count: int
    expense_cents: int = Field(description="Expenses of the period in the Vinted category")
    expense_count: int
    purchase_count: int
    extra_count: int
    balance_cents: int = Field(description="sales_cents - expense_cents; may be negative")
    sold_count: int = Field(description="Items whose sale falls in the period")
    sold_cents: int
    sold_cost_cents: int
    gain_cents: int = Field(description="sold_cents - sold_cost_cents")
