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


# --- merchants ----------------------------------------------------------

class MerchantOut(BaseModel):
    id: int
    name: str
    expense_count: int
    last_category_id: int | None


class MerchantUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class MerchantMerge(BaseModel):
    into_id: int


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


class SummaryOut(BaseModel):
    month: str
    total_cents: int = Field(description="Expenses of the month")
    expense_count: int
    by_category: list[CategoryTotal]
    income_cents: int = Field(description="Incomes of the month")
    income_count: int
    voucher_cents: int = Field(description="Part of income_cents in the category meal_voucher")
    balance_cents: int = Field(description="income_cents - total_cents; may be negative")


class MonthTotals(BaseModel):
    """One month of GET /summary/trend."""

    month: str
    income_cents: int
    income_count: int
    expense_cents: int
    expense_count: int
    voucher_cents: int = Field(description="Part of income_cents in the category meal_voucher")
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

VintedStatus = Literal["listed", "sold", "withdrawn"]


class VintedPurchaseIn(BaseModel):
    """The purchase of an item: a new expense in the Vinted category, or,
    with ``expense_id``, one already recorded there (for example from
    "Nuova spesa")."""

    expense_id: int | None = Field(default=None, description="An expense of the Vinted category, not linked yet")
    amount: str | None = Field(default=None, max_length=20, description="Total paid: price, shipping, fees")
    expense_date: date | None = None
    merchant: str | None = Field(default="Vinted", max_length=80, description="Where it was bought")
    paid_by_user_id: int | None = Field(default=None, description="Defaults to the logged-in user")
    payment_method: PaymentMethod = "card"


class VintedItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=300)
    listed_on: date | None = Field(
        default=None, description="On sale since: defaults to the purchase date, else today"
    )
    purchase: VintedPurchaseIn | None = Field(default=None, description="None for things already at home")
    client_uuid: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        description="Idempotency key: retrying with the same value never creates a duplicate",
    )


class VintedItemUpdate(BaseModel):
    """Partial update. ``"note": null`` clears the note."""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=300)
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


class VintedItemOut(BaseModel):
    id: int
    title: str
    note: str | None
    status: VintedStatus
    listed_on: date
    photo: str | None = Field(description="Version token of the photo, null without one")
    purchase: VintedPurchaseOut | None
    sale: VintedSaleOut | None
    gain_cents: int | None = Field(
        description="Sale minus purchase (an item without purchase costs zero); null until sold"
    )
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


class MessageOut(BaseModel):
    detail: str
