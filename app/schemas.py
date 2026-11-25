"""Pydantic models: the JSON contract of the API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

PaymentMethod = Literal["card", "cash", "other"]


# --- users and authentication -------------------------------------------

class UserOut(BaseModel):
    id: int
    display_name: str


class SetupUser(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=8, max_length=200)


class SetupIn(BaseModel):
    users: list[SetupUser] = Field(min_length=1, max_length=2)


class SetupStatus(BaseModel):
    needs_setup: bool


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class PasswordChangeIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)
    current_password: str | None = Field(default=None, max_length=200)


# --- categories ---------------------------------------------------------

class CategoryOut(BaseModel):
    id: int
    name: str
    sort_order: int
    is_active: bool
    expense_count: int
    system_key: str | None = Field(
        default=None,
        description="Set on a category the app itself relies on (\"vinted\"): "
        "it can be renamed, never deactivated or deleted",
    )


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    is_active: bool | None = None
    sort_order: int | None = None


class CategoryOrderIn(BaseModel):
    """PUT /categories/order (0.14.0): every category id, in the new order."""

    ids: list[int] = Field(min_length=1, max_length=200)


# --- merchants ----------------------------------------------------------

class MerchantOut(BaseModel):
    id: int
    name: str
    expense_count: int
    recent_count: int = Field(
        default=0, description="Expenses of the last 90 days (0.14.0): the list is sorted by it first"
    )
    last_category_id: int | None


class MerchantUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class MerchantMerge(BaseModel):
    into_id: int


class MerchantDistinctIn(BaseModel):
    """Two merchants that look alike but are different places (0.11.0)."""

    other_id: int


MerchantDuplicateReason = Literal["same", "contained", "similar"]


class MerchantDuplicateOut(BaseModel):
    """A possible duplicate (0.11.0): two merchants with names that look
    alike, the one with more expenses first."""

    reason: MerchantDuplicateReason = Field(
        description="same: the same name written differently; contained: one name inside the other;"
        " similar: one letter apart"
    )
    reason_name: str = Field(description="The reason in Italian, to show")
    merchants: list[MerchantOut] = Field(min_length=2, max_length=2)


# --- expenses -----------------------------------------------------------

class ExpenseCreate(BaseModel):
    amount: str = Field(max_length=20, description='Decimal text, comma or dot: "12,50"')
    category_id: int
    merchant: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=300)
    expense_date: date
    paid_by_user_id: int | None = Field(default=None, description="Defaults to the logged-in user")
    payment_method: PaymentMethod = "card"
    client_uuid: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        description="Idempotency key: retrying with the same value never creates a duplicate",
    )


class ExpenseUpdate(BaseModel):
    """Partial update: only the fields present in the body are changed."""

    amount: str | None = Field(default=None, max_length=20)
    category_id: int | None = None
    merchant: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=300)
    expense_date: date | None = None
    paid_by_user_id: int | None = None
    payment_method: PaymentMethod | None = None


class ExpenseOut(BaseModel):
    id: int
    amount_cents: int
    expense_date: date
    category_id: int
    category_name: str
    merchant_id: int | None
    merchant_name: str | None
    note: str | None
    paid_by_user_id: int
    paid_by_name: str
    payment_method: PaymentMethod
    created_by_user_id: int
    created_by_name: str
    created_at: str
    updated_at: str
    vinted_item_id: int | None = Field(
        default=None, description="The Vinted item this expense bought, if any"
    )
    vinted_item_title: str | None = None


class ExpenseDuplicateOut(BaseModel):
    """An expense that looks like the one just saved (0.14.0)."""

    id: int
    amount_cents: int
    expense_date: date
    merchant_name: str | None
    category_name: str
    paid_by_name: str
    created_by_user_id: int
    created_by_name: str
    created_at: str


class ExpenseCreatedOut(ExpenseOut):
    """Answer of POST /expenses: the saved expense, plus the ones that look
    like it (same amount and day, same merchant, or the same category when
    neither has a merchant). The expense is saved anyway: the list only lets
    the app say "it looks like a duplicate" next to its "Annulla"."""

    possible_duplicates: list[ExpenseDuplicateOut] = Field(default_factory=list)


class SearchMonthOut(BaseModel):
    month: str
    count: int
    total_cents: int


class SearchTotalsOut(BaseModel):
    """GET /summary/search/expenses and /summary/search/incomes (0.14.0):
    totals of every match of a search, also per month (newest first), while
    the list itself is read a page at a time (``limit`` and ``offset``)."""

    count: int
    total_cents: int
    months: list[SearchMonthOut]


# --- recurring expenses ---------------------------------------------------

class RecurringCreate(BaseModel):
    amount: str = Field(max_length=20, description="Proposed amount; can change at each registration")
    category_id: int
    merchant: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=300)
    paid_by_user_id: int | None = Field(default=None, description="Defaults to the logged-in user")
    payment_method: PaymentMethod = "card"
    interval_months: int = Field(ge=1, le=12, description="1 monthly, 2 bimonthly, 3 quarterly, 12 yearly")
    next_due: date = Field(description="First occurrence; its day of month is kept for the next ones")


class RecurringUpdate(BaseModel):
    """Partial update. Changing ``next_due`` also sets the day of month."""

    amount: str | None = Field(default=None, max_length=20)
    category_id: int | None = None
    merchant: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=300)
    paid_by_user_id: int | None = None
    payment_method: PaymentMethod | None = None
    interval_months: int | None = Field(default=None, ge=1, le=12)
    next_due: date | None = None
    is_active: bool | None = None


class RecurringOut(BaseModel):
    id: int
    amount_cents: int
    category_id: int
    category_name: str
    category_active: bool
    merchant_name: str | None
    note: str | None
    paid_by_user_id: int
    paid_by_name: str
    payment_method: PaymentMethod
    interval_months: int
    day_of_month: int
    next_due: date
    is_active: bool


class RecurringOccurrence(BaseModel):
    """Identifies the occurrence being registered or skipped.

    Must equal the template's current ``next_due``: if the other person has
    already handled it, the request is refused with 409 instead of creating
    a duplicate.
    """

    due_date: date


class RecurringRegister(RecurringOccurrence):
    """Fields left out are taken from the template; the date defaults to ``due_date``."""

    amount: str | None = Field(default=None, max_length=20)
    expense_date: date | None = None
    category_id: int | None = None
    merchant: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=300)
    paid_by_user_id: int | None = None
    payment_method: PaymentMethod | None = None
    client_uuid: str | None = Field(default=None, min_length=8, max_length=64)


class RecurringRegistered(BaseModel):
    expense: ExpenseOut
    recurring: RecurringOut


# --- incomes ------------------------------------------------------------

# Fixed list of income categories: code -> name shown in the app and in the
# CSV, in display order. Changing it is a code change, released as a new
# version. Codes are stored in incomes.category; a name can change freely.
INCOME_CATEGORIES = {
    "salary": "Stipendio",
    "refund": "Rimborsi",
    "gift": "Regali",
    "sale": "Vendite",
    # 0.8.0: sales on Vinted, linked to an item of the Vinted section.
    "vinted": "Vinted",
    "other": "Altro",
    # 0.7.0: the month's meal vouchers, registered as one income a month
    # (purchases paid with them are recorded as normal expenses, in full).
    "meal_voucher": "Buoni pasto",
}
IncomeCategory = Literal[tuple(INCOME_CATEGORIES)]


class IncomeCategoryOut(BaseModel):
    code: str
    name: str


class IncomeCreate(BaseModel):
    amount: str = Field(max_length=20, description='Decimal text, comma or dot: "1850,00"')
    category: IncomeCategory
    income_date: date
    note: str | None = Field(default=None, max_length=300)
    received_by_user_id: int | None = Field(default=None, description="Defaults to the logged-in user")
    client_uuid: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        description="Idempotency key: retrying with the same value never creates a duplicate",
    )


class IncomeUpdate(BaseModel):
    """Partial update: only the fields present in the body are changed."""

    amount: str | None = Field(default=None, max_length=20)
    category: IncomeCategory | None = None
    income_date: date | None = None
    note: str | None = Field(default=None, max_length=300)
    received_by_user_id: int | None = None


class IncomeOut(BaseModel):
    id: int
    amount_cents: int
    income_date: date
    category: str
    category_name: str
    note: str | None
    received_by_user_id: int
    received_by_name: str
    created_by_user_id: int
    created_by_name: str
    created_at: str
    updated_at: str
    vinted_item_id: int | None = Field(
        default=None, description="The Vinted item this income sold, if any"
    )
    vinted_item_title: str | None = None


# --- recurring incomes ----------------------------------------------------
# The twin of the recurring expense templates: same rules, own table.

class RecurringIncomeCreate(BaseModel):
    amount: str = Field(max_length=20, description="Proposed amount; can change at each registration")
    category: IncomeCategory
    note: str | None = Field(default=None, max_length=300)
    received_by_user_id: int | None = Field(default=None, description="Defaults to the logged-in user")
    interval_months: int = Field(ge=1, le=12, description="1 monthly, 2 bimonthly, 3 quarterly, 12 yearly")
    next_due: date = Field(description="First occurrence; its day of month is kept for the next ones")


class RecurringIncomeUpdate(BaseModel):
    """Partial update. Changing ``next_due`` also sets the day of month."""

    amount: str | None = Field(default=None, max_length=20)
    category: IncomeCategory | None = None
    note: str | None = Field(default=None, max_length=300)
    received_by_user_id: int | None = None
    interval_months: int | None = Field(default=None, ge=1, le=12)
    next_due: date | None = None
    is_active: bool | None = None


class RecurringIncomeOut(BaseModel):
    id: int
    amount_cents: int
    category: str
    category_name: str
    note: str | None
    received_by_user_id: int
    received_by_name: str
    interval_months: int
    day_of_month: int
    next_due: date
    is_active: bool


class RecurringIncomeRegister(RecurringOccurrence):
    """Fields left out are taken from the template; the date defaults to ``due_date``."""

    amount: str | None = Field(default=None, max_length=20)
    income_date: date | None = None
    category: IncomeCategory | None = None
    note: str | None = Field(default=None, max_length=300)
    received_by_user_id: int | None = None
    client_uuid: str | None = Field(default=None, min_length=8, max_length=64)


class RecurringIncomeRegistered(BaseModel):
    income: IncomeOut
    recurring: RecurringIncomeOut


# --- summary ------------------------------------------------------------

class CategoryTotal(BaseModel):
    category_id: int
    category_name: str
    total_cents: int
    expense_count: int


class ExpectedIncomeOut(BaseModel):
    """A recurring income due in the month and not registered yet (0.14.0)."""

    recurring_id: int
    category: str
    category_name: str
    received_by_name: str
    due_date: date
    amount_cents: int = Field(description="The template's proposed amount")


class SummaryOut(BaseModel):
    month: str
    total_cents: int = Field(description="Expenses of the month")
    expense_count: int
    by_category: list[CategoryTotal]
    income_cents: int = Field(description="Incomes of the month")
    income_count: int
    voucher_cents: int = Field(description="Part of income_cents in the category meal_voucher")
    balance_cents: int = Field(description="income_cents - total_cents; may be negative")
    expected_income_cents: int = Field(
        default=0,
        description="Active recurring incomes due in the month and not registered yet (0.14.0)",
    )
    expected_incomes: list[ExpectedIncomeOut] = Field(default_factory=list)


class MonthTotals(BaseModel):
    """One month of GET /summary/trend."""

    month: str
    income_cents: int
    income_count: int
    expense_cents: int
    expense_count: int
    voucher_cents: int = Field(description="Part of income_cents in the category meal_voucher")
    balance_cents: int = Field(description="income_cents - expense_cents; may be negative")


class PeriodTotalsOut(BaseModel):
    """GET /summary/period (0.9.0): the totals of any period, for "Esplora"."""

    start: date
    end: date
    income_cents: int
    income_count: int
    voucher_cents: int = Field(description="Part of income_cents in the category meal_voucher")
    expense_cents: int
    expense_count: int
    balance_cents: int = Field(description="income_cents - expense_cents; may be negative")


class IncomeCategoryTotal(BaseModel):
    category: str
    category_name: str
    total_cents: int
    income_count: int


class IncomeSummaryOut(BaseModel):
    """GET /summary/incomes: the incomes of a month by category."""

    month: str
    total_cents: int
    income_count: int
    by_category: list[IncomeCategoryTotal]


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


# --- backups and exports (0.14.0) ------------------------------------------

BackupCopyKind = Literal["daily", "pre_update", "pre_restore"]


class BackupCopyOut(BaseModel):
    name: str = Field(description="File name, to restore it with POST /backups/{name}/restore")
    kind: BackupCopyKind = Field(
        description="daily: the copy of the day; pre_update: before an update changed the"
        " database; pre_restore: the data replaced by a restore"
    )
    created_at: str = Field(description="ISO 8601 UTC")
    size_bytes: int


class BackupDownloadOut(BaseModel):
    at: str = Field(description="ISO 8601 UTC")
    user_name: str


class BackupsOut(BaseModel):
    last_download: BackupDownloadOut | None = Field(description="The last GET /backup, by anyone")
    copies: list[BackupCopyOut] = Field(description="Copies kept on the server, newest first")


class ExportFileOut(BaseModel):
    name: str
    url: str = Field(description="Path of the CSV, relative to the server")


class ExportBriefOut(BaseModel):
    """GET /export/brief (0.14.0): the CSV files of a period and a short
    text to send with them to an AI assistant: what the files hold, the
    totals to check them against and the app's conventions."""

    text: str
    files: list[ExportFileOut]


class MessageOut(BaseModel):
    detail: str
