"""0.18.0 on a phone-sized Chrome: Movimenti opens on the calendar (F15),
the lens with the filters (F6) and the tags of the notes (F2), the new
Riepilogo (R1) and the incomes of a category highlighted."""

from __future__ import annotations

from datetime import date

from tests_ui.conftest import unexpected_errors
from tests_ui.test_phone import plain

# A month that is over: the day the calendar opens on does not depend on
# today (and on the clock near midnight).
FIRST = date.today().replace(day=1)
PAST = (FIRST.replace(year=FIRST.year - 1, month=12) if FIRST.month == 1 else FIRST.replace(month=FIRST.month - 1))
PAST_MONTH = PAST.strftime("%Y-%m")


def day(number: int) -> str:
    return PAST.replace(day=number).isoformat()


def categories(api):
    return {c["name"]: c["id"] for c in api.get("/categories").json()}


def users(api):
    return {u["display_name"]: u["id"] for u in api.get("/users").json()}


def expense(api, amount, merchant, on, category="Spesa alimentare", who="Fabio", note=None):
    body = {"amount": amount, "merchant": merchant, "category_id": categories(api)[category],
            "expense_date": on, "paid_by_user_id": users(api)[who]}
    if note:
        body["note"] = note
    api.post("/expenses", json=body).raise_for_status()


def test_calendar_opens_a_past_month_on_its_last_day_with_expenses(phone, api, server):
    expense(api, "12,30", "Lidl", day(10))
    expense(api, "40", "Coop", day(20), who="Nastia")
    expense(api, "7,70", "Bar", day(20))
    phone.goto(f"{server}/movimenti?mese={PAST_MONTH}")
    selected = phone.wait_for_selector(".cal-day.is-selected")
    assert selected.inner_text().split() == ["20", "48"]  # 40 + 7,70, whole euros
    receipt = phone.locator(".cal-receipt")
    assert "Coop" in receipt.inner_text() and "Bar" in receipt.inner_text()
    assert "47,70" in plain(receipt.locator(".day-total").inner_text())

    phone.click(".cal-day:has(.cal-num:text-is('10'))")
    phone.wait_for_selector(".cal-receipt:has-text('Lidl')")
    assert f"giorno={day(10)}" in phone.url
    phone.click(".cal-receipt .row:has-text('Lidl')")
    phone.wait_for_selector("#expense-amount")
    phone.go_back()
    phone.wait_for_selector(".cal-day.is-selected:has(.cal-num:text-is('10'))")

    # A day without expenses: the way to add one on that day.
    phone.click(".cal-day:has(.cal-num:text-is('12'))")
    phone.click("a:has-text('Aggiungi una spesa in questo giorno')")
    phone.wait_for_selector("#expense-amount")
    assert phone.eval_on_selector("#expense-date", "(node) => node.value") == day(12)
    assert unexpected_errors(phone) == []


def test_lens_filters_and_tags(phone, api, server):
    expense(api, "86", "Trenitalia", day(5), "Auto e trasporti", note="Andata #Mare")
    expense(api, "420", "Hotel", day(6), "Svago", who="Nastia", note="Tre notti #mare")
    expense(api, "15", "Lidl", day(7), who="Nastia")
    phone.goto(f"{server}/movimenti?mese={PAST_MONTH}")
    phone.wait_for_selector(".cal")
    phone.click("button[aria-label='Lista del mese e ricerca']")
    phone.wait_for_selector("#expense-search")
    assert phone.locator(".roll .row").count() == 3
    assert not phone.eval_on_selector("#expense-search", "(node) => node === document.activeElement")

    # Who paid: from the sheet; the pill turns green with the name and ×.
    phone.click(".pill:has-text('Chi')")
    phone.click(".dialog.is-sheet .dialog-option:has-text('Nastia')")
    phone.wait_for_selector(".pill.is-active:has-text('Nastia')")
    phone.wait_for_selector(".search-scope")
    assert "435,00" in plain(phone.locator(".month-total-amount").inner_text())
    assert "chi=" in phone.url
    phone.click("button[aria-label='Togli il filtro Chi']")
    phone.wait_for_selector(".pill:has-text('Chi') .pill-caret")

    # A tag under a row: every expense with it, in any spelling, with the total.
    phone.click(".tag-pill:has-text('#mare')")
    phone.wait_for_selector(".pill.is-active:has-text('#mare')")
    phone.wait_for_selector(".search-scope")
    assert phone.locator(".roll .row").count() == 2
    assert "506,00" in plain(phone.locator(".month-total-amount").inner_text())
    # The note under the row without its tag.
    assert phone.locator(".row:has-text('Hotel') .row-note").inner_text() == "Tre notti"

    # Back returns to the calendar.
    phone.go_back()
    phone.go_back()
    phone.wait_for_selector(".cal")
    assert unexpected_errors(phone) == []


def test_note_suggests_the_tags_already_used(phone, api, server):
    expense(api, "86", "Trenitalia", day(5), note="#mare-2026")
    phone.goto(f"{server}/")
    phone.wait_for_selector("#expense-amount")
    phone.click(".more-bar")
    phone.click("#expense-note")
    phone.keyboard.type("Gelato #ma")
    phone.click(".tag-chips .chip:has-text('#mare-2026')")
    assert phone.eval_on_selector("#expense-note", "(node) => node.value") == "Gelato #mare-2026 "
    assert unexpected_errors(phone) == []


def test_summary_ledger_bars_and_income_categories(phone, api, server):
    expense(api, "100", "Coop", day(3))
    api.post("/incomes", json={"amount": "1850", "category": "salary", "income_date": day(4)}).raise_for_status()
    api.post("/incomes", json={"amount": "160", "category": "meal_voucher",
                               "income_date": day(5)}).raise_for_status()
    phone.goto(f"{server}/riepilogo")
    phone.wait_for_selector(".ledger")
    columns = phone.locator(".trend-col")
    assert columns.count() == 6
    before = columns.all_inner_texts()
    phone.click(f".trend-col:nth-child(5)")  # the month before the current one
    phone.wait_for_selector(".ledger-line.is-final:has-text('Differenza')")
    ledger = plain(phone.locator(".ledger").inner_text())
    assert "2.010,00 €" in ledger and "di cui buoni pasto" in ledger and "− 100,00 €" in ledger
    assert "+ 1.910,00 €" in plain(phone.locator(".ledger-line.is-final").inner_text())
    assert columns.all_inner_texts() == before  # the columns stay where they are
    assert f"mese={PAST_MONTH}" in phone.url

    phone.click(".seg-side .seg-item:has-text('Entrate')")
    phone.click(".bar:has-text('Buoni pasto')")
    phone.wait_for_selector(".slip-row.is-marked")
    assert phone.locator(".slip-row.is-marked").count() == 1
    assert "Evidenziate: Buoni pasto · 160,00 €" in plain(phone.locator(".slip-marked").inner_text())
    phone.click("button[aria-label='Togli l’evidenza']")
    assert phone.locator(".slip-row.is-marked").count() == 0
    phone.go_back()
    phone.wait_for_selector(".seg-side .seg-item.is-selected:has-text('Entrate')")
    assert unexpected_errors(phone) == []
