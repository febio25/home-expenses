"""Markdowns of the Vinted items on sale (0.19.0, F7): the price goes down
a step every few days, down to the minimum, and never by itself. The app
only says when a step is due and to what price; the user changes the price
on Vinted, then confirms it here.

Rules decided with Fabio and Nastia (22-23/11 and 27/11/2026):
- a base plan, the same for every item without a plan of its own: 10%
  every 14 days, counted from the day of publication, then from the last
  change of price (or the last «Salta»);
- a plan of its own per item, proposed by Claude in the answer (a line
  «RIBASSO: 10% ogni 14 giorni», «2 € ogni 7 giorni» or «niente») or
  written by hand;
- the new price is rounded down to half a euro and is never below the
  minimum; without a minimum there is nothing to mark down to;
- at the minimum, one more round at that price; then, still unsold, the
  item asks for a decision (ask Claude again, withdraw, or leave it so).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from .money import AmountError, format_cents, parse_amount

# The base plan. Fixed for now; an item without a plan of its own follows
# it, so making it a setting later needs no migration.
BASE_KIND = "pct"
BASE_AMOUNT = 10
BASE_DAYS = 14

STEP_CENTS = 50  # prices go down to the half euro
MAX_PCT = 50
MAX_DAYS = 90
MAX_EUR_CENTS = 100_000
MAX_STEPS = 24  # the steps listed ahead, a bound for odd plans

_NOTHING = re.compile(r"^(niente|nulla|nessun[oa]?|no|non ribassare|mai)\b", re.IGNORECASE)
_AMOUNT = re.compile(r"(\d+(?:[.,]\d{1,2})?)\s*(%|€|euro|eur)", re.IGNORECASE)
_DAYS = re.compile(r"ogni\s+(\d+)?\s*(giorni|giorno|gg|settimane|settimana)\b", re.IGNORECASE)


def base_plan() -> dict:
    return {"kind": BASE_KIND, "amount": BASE_AMOUNT, "days": BASE_DAYS, "source": "base"}


def plan_of(row) -> dict:
    """The plan of an item (a row of vinted_items): its own, else the base."""
    kind = row["markdown_kind"]
    if kind is None:
        return base_plan()
    source = row["markdown_source"] or "manual"
    if kind == "none":
        return {"kind": "none", "amount": None, "days": None, "source": source}
    return {"kind": kind, "amount": row["markdown_amount"], "days": row["markdown_days"], "source": source}


def describe(plan: dict) -> str:
    """"−10% ogni 14 giorni", "−2,50 € ogni 7 giorni", "Niente ribasso"."""
    if plan["kind"] == "none":
        return "Niente ribasso"
    every = "ogni giorno" if plan["days"] == 1 else f"ogni {plan['days']} giorni"
    if plan["kind"] == "pct":
        return f"−{plan['amount']}% {every}"
    cents = plan["amount"]
    euros = str(cents // 100) if cents % 100 == 0 else format_cents(cents, ",")
    return f"−{euros} € {every}"


def parse_plan(text: str | None) -> dict | None:
    """A plan written in words, as in the line RIBASSO of Claude's answer:
    "10% ogni 14 giorni", "2 € ogni settimana", "niente". None when it
    cannot be read safely (then the item keeps its plan)."""
    if not text:
        return None
    value = " ".join(text.replace("*", " ").split()).strip(" .«»\"'")
    if not value:
        return None
    if _NOTHING.match(value):
        return {"kind": "none", "amount": None, "days": None}
    amount = _AMOUNT.search(value)
    days = _DAYS.search(value)
    if not amount or not days:
        return None
    number, unit = amount.group(1), amount.group(2)
    count = int(days.group(1)) if days.group(1) else 1
    every = count * 7 if days.group(2).lower().startswith("settiman") else count
    if not 1 <= every <= MAX_DAYS:
        return None
    if unit == "%":
        if not re.fullmatch(r"\d+", number) or not 1 <= int(number) <= MAX_PCT:
            return None
        return {"kind": "pct", "amount": int(number), "days": every}
    try:
        cents = parse_amount(number)
    except AmountError:
        return None
    if not STEP_CENTS <= cents <= MAX_EUR_CENTS:
        return None
    return {"kind": "eur", "amount": cents, "days": every}


def next_price(price: int, minimum: int, plan: dict) -> int:
    """One step down from price: rounded down to the half euro, at least
    half a euro less, never below the minimum."""
    if plan["kind"] == "pct":
        lower = price * (100 - plan["amount"]) // 100
    else:
        lower = price - plan["amount"]
    lower = lower // STEP_CENTS * STEP_CENTS
    if lower >= price:
        lower = price - STEP_CENTS
    return max(minimum, lower)


def steps_ahead(price: int, minimum: int, plan: dict) -> list[int]:
    """The prices of the steps to come, the next first, the minimum last."""
    steps: list[int] = []
    while price > minimum and len(steps) < MAX_STEPS:
        price = next_price(price, minimum, plan)
        steps.append(price)
    return steps


def state_of(item: dict, row, today: date) -> dict:
    """Where an item stands (item as built by item_out, row its row):

    - inactive: not on sale on Vinted (not published, sold, withdrawn) or
      without a price;
    - off: plan «Niente ribasso»;
    - no_minimum: on sale, but without a minimum there is no floor;
    - waiting / due: above the minimum, the next step is not due yet / is;
    - at_minimum / review: at the minimum, for less than a round / for a
      whole round, still unsold: a decision is asked;
    - settled: «Lascia così» at the minimum, since the last change of price.
    """
    plan = plan_of(row)
    result = {
        "plan": {**plan, "text": describe(plan)},
        "state": "inactive",
        "since": None,
        "due_on": None,
        "next_price_cents": None,
        "steps": [],
    }
    listing = item["listing"]
    price, minimum = listing["price_cents"], listing["min_price_cents"]
    if item["status"] != "listed" or item["listed_on"] is None or price is None:
        return result
    if plan["kind"] == "none":
        result["state"] = "off"
        return result
    if minimum is None:
        result["state"] = "no_minimum"
        return result
    changes = listing["price_changes"]
    since = date.fromisoformat(str(changes[-1]["changed_on"] if changes else item["listed_on"]))
    result["since"] = since.isoformat()
    anchor = since
    skipped = row["markdown_skipped_on"]
    if skipped and date.fromisoformat(skipped) > anchor:
        anchor = date.fromisoformat(skipped)
    due_on = anchor + timedelta(days=plan["days"])
    result["due_on"] = due_on.isoformat()
    if price > minimum:
        result["state"] = "due" if today >= due_on else "waiting"
        result["steps"] = steps_ahead(price, minimum, plan)
        result["next_price_cents"] = result["steps"][0]
        return result
    settled = row["markdown_settled_on"]
    if settled and date.fromisoformat(settled) >= since:
        result["state"] = "settled"
    else:
        result["state"] = "review" if today >= due_on else "at_minimum"
    return result


def plan_columns(plan: dict | None, source: str) -> dict:
    """The columns of vinted_items for a plan: None is the base plan."""
    if plan is None:
        return {"markdown_kind": None, "markdown_amount": None, "markdown_days": None, "markdown_source": None}
    return {
        "markdown_kind": plan["kind"],
        "markdown_amount": plan.get("amount"),
        "markdown_days": plan.get("days"),
        "markdown_source": source,
    }


__all__ = [
    "BASE_AMOUNT", "BASE_DAYS", "base_plan", "plan_of", "describe", "parse_plan", "next_price",
    "steps_ahead", "state_of", "plan_columns",
]
