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


# --- summary ------------------------------------------------------------

class CategoryTotal(BaseModel):
    category_id: int
    category_name: str
    total_cents: int
    expense_count: int


class SummaryOut(BaseModel):
    month: str
    total_cents: int
    expense_count: int
    by_category: list[CategoryTotal]


class MessageOut(BaseModel):
    detail: str
