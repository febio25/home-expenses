"""Date-range handling shared by the list, summary and export endpoints."""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from fastapi import HTTPException

_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")

# Expense dates outside this window are almost certainly typos (a year
# typed as 2062, a date picker scrolled too far) and would land in months
# nobody ever opens.
EARLIEST_EXPENSE_DATE = date(2000, 1, 1)
# The container clock is UTC while the phones are in Italy (one or two hours
# ahead), so "today" on the phone can be "tomorrow" for the server.
FUTURE_TOLERANCE = timedelta(days=1)


def today() -> date:
    """Server date. A function so tests can pin it."""
    return date.today()


def check_expense_date(value: date) -> None:
    """Reject expense (and income) dates in the future or before 2000 (422)."""
    if value < EARLIEST_EXPENSE_DATE:
        raise HTTPException(status_code=422, detail="Data non valida: deve essere dal 2000 in poi.")
    if value > today() + FUTURE_TOLERANCE:
        raise HTTPException(status_code=422, detail="La data non può essere nel futuro.")


def month_bounds(month: str) -> tuple[date, date]:
    """First and last day of a "YYYY-MM" month."""
    match = _MONTH.match(month)
    if not match:
        raise HTTPException(status_code=422, detail="Mese non valido: usa il formato AAAA-MM.")
    year, month_number = int(match.group(1)), int(match.group(2))
    if year < 1:  # "0000-01" matches the pattern but is no date
        raise HTTPException(status_code=422, detail="Mese non valido: usa il formato AAAA-MM.")
    last_day = calendar.monthrange(year, month_number)[1]
    return date(year, month_number, 1), date(year, month_number, last_day)


def add_months(start: date, months: int, day_of_month: int) -> date:
    """The date ``months`` after ``start``, on ``day_of_month``.

    The day is clamped to the length of the target month and restored later:
    with day 31, 31 Jan -> 28 Feb -> 31 Mar.
    """
    index = start.year * 12 + (start.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day_of_month, last_day))


def due_day_after_change(new_due: date, current_day: int) -> int:
    """Day of month a template keeps when its next due date is moved by hand.

    A date clamped to the end of a short month (day 31 -> 30 Nov, as an
    "Annulla" puts it back) keeps the original day; any other date sets a
    new day of month. Shared by expense and income templates.
    """
    last_day = calendar.monthrange(new_due.year, new_due.month)[1]
    clamped = new_due.day == last_day and current_day > last_day
    return current_day if clamped else new_due.day


def resolve_range(
    month: str | None, date_from: date | None, date_to: date | None
) -> tuple[date | None, date | None]:
    """Turn the query parameters into an inclusive (start, end) range.

    ``month`` wins over from/to. Either bound may be None (open range).
    """
    if month:
        return month_bounds(month)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422, detail="La data iniziale deve precedere quella finale."
        )
    return date_from, date_to


def range_filter(
    start: date | None, end: date | None, column: str = "e.expense_date"
) -> tuple[str, list[str]]:
    """SQL WHERE fragment (possibly empty) and its parameters."""
    clauses, params = [], []
    if start:
        clauses.append(f"{column} >= ?")
        params.append(start.isoformat())
    if end:
        clauses.append(f"{column} <= ?")
        params.append(end.isoformat())
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params
