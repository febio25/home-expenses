"""Pydantic models: the JSON contract of the API.

The models of the Vinted section are in vinted_schemas.py (0.17.0).
"""

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
    icon: str = Field(
        default="category",
        description="Name of the category's icon (0.15.0), one of GET /categories/icons; "
        "the default one when none was chosen",
    )


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    icon: str | None = Field(default=None, max_length=40, description="One of GET /categories/icons")


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    is_active: bool | None = None
    sort_order: int | None = None
    icon: str | None = Field(default=None, max_length=40, description="One of GET /categories/icons")


class CategoryIconsOut(BaseModel):
    """GET /categories/icons (0.15.0): the icons a category can have."""

    icons: list[str]
    default: str


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
    is_variable: bool = Field(default=False, description="0.17.0: the amount changes each time; the stored one is an estimate")


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
    is_variable: bool | None = None


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
    is_variable: bool


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
    # 0.7.0: the month's meal vouchers, registered as one income a month
    # (purchases paid with them are recorded as normal expenses, in full).
    "meal_voucher": "Buoni pasto",
    # 0.8.0: sales on Vinted, linked to an item of the Vinted section.
    "vinted": "Vinted",
    "refund": "Rimborsi",
    "gift": "Regali",
    "sale": "Vendite",
    "other": "Altro",
}
# 0.16.0: the order follows how often each one is used (Stipendio, Buoni
# pasto, Vinted first, Altro last).
IncomeCategory = Literal[tuple(INCOME_CATEGORIES)]


class IncomeCategoryOut(BaseModel):
    code: str
    name: str
    icon: str = Field(default="category", description="Name of the category's icon (0.15.0), fixed")


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
    is_variable: bool = Field(default=False, description="0.17.0: the amount changes each time; the stored one is an estimate")


class RecurringIncomeUpdate(BaseModel):
    """Partial update. Changing ``next_due`` also sets the day of month."""

    amount: str | None = Field(default=None, max_length=20)
    category: IncomeCategory | None = None
    note: str | None = Field(default=None, max_length=300)
    received_by_user_id: int | None = None
    interval_months: int | None = Field(default=None, ge=1, le=12)
    next_due: date | None = None
    is_active: bool | None = None
    is_variable: bool | None = None


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
    is_variable: bool


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


class RecurringCostSide(BaseModel):
    """The active templates of one kind, as a monthly and a yearly amount."""

    count: int = Field(description="Active templates")
    month_cents: int = Field(description="Sum of amount / interval in months, rounded to the cent")
    year_cents: int = Field(description="Sum of amount * 12 / interval in months, rounded to the cent")
    has_variable: bool = Field(description="At least one of them has a variable amount: the totals are estimates")


class RecurringCostsOut(BaseModel):
    """0.17.0: what the recurring items cost (and bring) a month and a year."""

    expenses: RecurringCostSide
    incomes: RecurringCostSide


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
