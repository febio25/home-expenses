"""0.18.1 on a phone-sized Chrome: the calendar with its tiles, the days of
the months around and the amounts in "k"; a day of one expense closes
without «Subtotale» in the lens but keeps it on the calendar; the lens of
Vinted in the head of the page, away from the filters; Vinted → Riepilogo
as a ledger like the household one."""

from __future__ import annotations

from datetime import date

import pytest

from tests_ui.conftest import open_phone, unexpected_errors
from tests_ui.test_0_18 import categories, expense
from tests_ui.test_phone import plain

# March 2026 starts on a Sunday and ends on a Tuesday: its grid shows six
# days of February and five of April. Over, whatever today is.
MONTH = "2026-03"


def tile(page, number, other=False):
    state = ".is-other" if other else ":not(.is-other)"
    return page.locator(f".cal-day{state}:has(.cal-num:text-is('{number}'))")


def test_calendar_tiles_days_around_and_big_amounts(phone, api, server):
    expense(api, "12,30", "Lidl", "2026-02-27")
    expense(api, "1240", "Mobilificio", "2026-03-10", "Casa e utenze")
    expense(api, "4,50", "Bar", "2026-03-11")
    phone.goto(f"{server}/movimenti?mese={MONTH}")
    phone.wait_for_selector(".cal")
    assert phone.locator(".cal-day.is-other").count() == 11

    big = tile(phone, "10")
    assert plain(big.inner_text()).split() == ["10", "1,2k", "€"]
    assert "heat-3" in big.get_attribute("class")
    assert "heat-1" in tile(phone, "11").get_attribute("class")
    empty = tile(phone, "12").get_attribute("class")
    assert "heat" not in empty and "is-other" not in empty

    # A day of February: the calendar moves to February, on that day, and
    # its receipt keeps «Subtotale» with one expense.
    tile(phone, "27", other=True).click()
    phone.wait_for_selector(".cal-day.is-selected:has(.cal-num:text-is('27'))")
    assert "mese=2026-02" in phone.url
    receipt = phone.locator(".cal-receipt")
    assert "Lidl" in receipt.inner_text()
    assert "12,30" in plain(receipt.locator(".day-sub").inner_text())

    # The lens: the same day of one expense closes with nothing.
    phone.click("button[aria-label='Lista del mese e ricerca']")
    phone.wait_for_selector(".roll .row:has-text('Lidl')")
    assert phone.locator(".roll .day-sub").count() == 0
    assert unexpected_errors(phone) == []


def test_lens_closes_a_day_of_one_expense_without_subtotal(phone, api, server):
    expense(api, "20", "Coop", "2026-03-04")
    expense(api, "5", "Bar", "2026-03-04")
    expense(api, "9", "Edicola", "2026-03-05")
    phone.goto(f"{server}/movimenti?vista=lista&mese={MONTH}")
    phone.wait_for_selector(".roll .row:has-text('Edicola')")
    days = phone.locator(".roll section.day")
    assert days.count() == 2
    assert days.nth(0).locator(".day-sub").count() == 0  # 5 March: Edicola alone
    assert "25,00" in plain(days.nth(1).locator(".day-sub").inner_text())


@pytest.mark.parametrize("size", ["360", "320"])
def test_vinted_lens_in_the_head_leaves_the_filters_their_row(browser, server, api, size):
    today = date.today().isoformat()
    for title in ("Giacca di lana", "Borsa a tracolla"):
        api.post("/vinted/items", json={"title": title, "listed_on": today}).raise_for_status()
    page = open_phone(browser, server, size)
    page.goto(f"{server}/vinted?filtro=tutti")
    page.wait_for_selector(".art-row, .row")
    lens = page.locator(".page-head button[aria-label='Cerca un articolo']")
    assert lens.get_attribute("aria-expanded") == "false"
    assert not page.locator("#vinted-search").is_visible()

    width = page.viewport_size["width"]
    pills = page.locator(".pills-icons .pill")
    assert pills.count() == 4
    for index in range(4):
        box = pills.nth(index).bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width

    lens.click()
    assert page.eval_on_selector("#vinted-search", "(node) => node === document.activeElement")
    assert lens.get_attribute("aria-expanded") == "true"
    bar = page.locator(".vinted-search").bounding_box()
    first = pills.nth(0).bounding_box()
    assert bar["y"] + bar["height"] <= first["y"]  # the bar never covers the icons
    page.keyboard.type("giacca")
    page.wait_for_selector("text=1 articolo trovato")

    lens.click()  # the lens again: empty and closed
    assert not page.locator("#vinted-search").is_visible()
    page.wait_for_selector("text=Tutti gli articoli")
    lens.click()
    page.keyboard.type("borsa")
    page.click("button[aria-label='Chiudi la ricerca']")
    assert not page.locator("#vinted-search").is_visible()
    assert page.eval_on_selector("#vinted-search", "(node) => node.value") == ""
    assert unexpected_errors(page) == []
    page.context.close()


def test_vinted_summary_is_a_ledger(phone, api, server):
    today = date.today().isoformat()
    item = api.post("/vinted/items", json={
        "title": "Sneakers", "listed_on": today,
        "purchase": {"amount": "30", "expense_date": today},
    })
    item.raise_for_status()
    api.post(f"/vinted/items/{item.json()['id']}/sale",
             json={"amount": "46", "income_date": today}).raise_for_status()
    expense(api, "4,50", "Buste", today, "Vinted")
    assert "Vinted" in categories(api)

    phone.goto(f"{server}/vinted/riepilogo")
    ledger = phone.wait_for_selector(".card.ledger")
    text = plain(ledger.inner_text())
    assert "Vendite (1)" in text and "Spese Vinted (2)" in text
    assert "di cui acquisti" in text and "di cui extra" in text
    assert "+ 11,50" in text  # 46 − 30 − 4,50
    page_text = phone.inner_text("main") if phone.locator("main").count() else phone.inner_text("body")
    assert "Articoli venduti nel mese" not in page_text
    assert phone.locator("a:has-text('Esplora')").count() == 1

    phone.click(".ledger-link:has-text('Vendite')")
    phone.wait_for_selector(".pill.is-selected[aria-label^='Venduti']")
    assert unexpected_errors(phone) == []
