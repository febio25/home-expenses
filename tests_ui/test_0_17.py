"""0.17.0 on a phone-sized Chrome: «Quanto costano» at the top of
Ricorrenti, «circa» before a variable amount, the «Importo variabile» box
and «4 mesi» in the form of a template."""

from __future__ import annotations

from datetime import date, timedelta

from tests_ui.conftest import unexpected_errors
from tests_ui.test_phone import plain

# Far from today: the browser and the test may not agree on the date near
# midnight, and these tests are not about the due date.
LATER = (date.today() + timedelta(days=40)).isoformat()


def categories(api):
    return {c["name"]: c["id"] for c in api.get("/categories").json()}


def test_costs_and_circa(phone, api, server):
    cats = categories(api)
    api.post("/recurring", json={"amount": "12", "category_id": cats["Abbonamenti"], "merchant": "Netflix",
                                 "interval_months": 1, "next_due": LATER}).raise_for_status()
    api.post("/recurring", json={"amount": "120", "category_id": cats["Casa e utenze"], "merchant": "Enel",
                                 "interval_months": 2, "next_due": LATER, "is_variable": True}).raise_for_status()
    api.post("/recurring-incomes", json={"amount": "2100", "category": "salary", "interval_months": 1,
                                         "next_due": LATER}).raise_for_status()
    phone.goto(f"{server}/ricorrenti")
    costs = phone.wait_for_selector(".costs")
    rows = phone.locator(".costs-row:not(.costs-head)")
    expenses = plain(rows.nth(0).inner_text())
    assert "Spese" in expenses and "(2)" in expenses
    assert "~" in expenses and "−72 €" in expenses and "−864 €" in expenses  # 12 + 120/2 a month
    incomes = plain(rows.nth(1).inner_text())
    assert "+2.100 €" in incomes and "+25.200 €" in incomes and "~" not in incomes
    assert "importi variabili" in costs.inner_text()
    enel = phone.locator(".row:has-text('Enel')")
    assert "circa" in enel.inner_text()
    assert "circa" not in phone.locator(".row:has-text('Netflix')").inner_text()
    assert unexpected_errors(phone) == []


def test_variable_box_and_four_months(phone, api, server):
    phone.goto(f"{server}/ricorrenti/nuova")
    phone.wait_for_selector("#expense-variable")
    phone.fill("#expense-amount", "140")
    phone.fill("#expense-merchant", "Bolletta gas")
    phone.click(".cat[aria-label='Casa e utenze']")
    phone.check("#expense-variable")
    phone.click(".seg-item:has-text('4 mesi')")
    phone.click(".footer-bar .btn-primary")
    phone.wait_for_url(f"{server}/ricorrenti")
    [template] = api.get("/recurring").json()
    assert template["is_variable"] is True and template["interval_months"] == 4
    assert template["amount_cents"] == 14000
    # The box keeps its state when the template is opened again.
    phone.goto(f"{server}/ricorrenti/{template['id']}")
    assert phone.wait_for_selector("#expense-variable").is_checked()
    # Incomes have it too.
    phone.goto(f"{server}/ricorrenti/entrate/nuova")
    assert not phone.wait_for_selector("#income-variable").is_checked()
    assert unexpected_errors(phone) == []
