"""The main flows on a phone-sized Chrome (0.14.0): the same scenarios used
by hand in the reviews, now repeatable. Dates follow the real calendar:
the server and the page both use today."""

from __future__ import annotations

import calendar
from datetime import date

import pytest

from tests_ui.conftest import open_phone, unexpected_errors

ROUTES = ["/", "/movimenti", "/entrate", "/riepilogo", "/riepilogo/entrate", "/vinted",
          "/vinted/riepilogo", "/impostazioni", "/ricorrenti", "/movimenti?cerca=bar"]


def plain(text: str) -> str:
    """Text as read on screen: the euro amounts use no-break spaces."""
    return text.replace(" ", " ")


def add_expense(api, **overrides):
    categories = {c["name"]: c["id"] for c in api.get("/categories").json()}
    body = {
        "amount": "12,50", "merchant": "Lidl", "category_id": categories["Spesa alimentare"],
        "expense_date": date.today().isoformat(),
    }
    body.update(overrides)
    response = api.post("/expenses", json=body)
    response.raise_for_status()
    return response.json()


def save(phone, amount, merchant, category):
    phone.fill("#expense-amount", amount)
    phone.fill("#expense-merchant", merchant)
    phone.click(f".cat[aria-label='{category}']")  # 0.15.0: icons, the name is the label
    phone.click(".btn-save")


# --- Nuova spesa ---------------------------------------------------------------------------


def test_save_and_undo_an_expense(phone):
    assert phone.evaluate("() => document.activeElement.id") == "expense-amount"
    save(phone, "12,50", "Bar Centrale", "Ristoranti e bar")
    toast = phone.wait_for_selector(".toast-success")
    assert plain(toast.inner_text()).startswith("Salvata: 12,50 € da Bar Centrale")
    phone.click(".toast-action")
    phone.wait_for_selector(".toast:has-text('Spesa annullata.')")
    assert unexpected_errors(phone) == []


def test_the_form_opens_and_keeps_the_amount_without_network(phone, server):
    """0.14.0: the lists of the last time are on the phone."""
    phone.context.route("**/api/**", lambda route: route.abort("internetdisconnected"))
    phone.goto(f"{server}/")
    phone.wait_for_selector("#expense-amount")
    assert phone.locator(".cat").count() == 11
    save(phone, "9,90", "Edicola", "Varie")
    banner = phone.wait_for_selector(".banner-error:not([hidden])")
    assert "La connessione è caduta" in banner.inner_text()
    assert phone.input_value("#expense-amount") == "9,90"
    phone.context.unroute("**/api/**")
    phone.click(".btn-save")
    assert plain(phone.wait_for_selector(".toast-success").inner_text()).startswith("Salvata: 9,90 €")


def test_an_expired_session_still_leads_to_the_login(phone, server):
    """The lists on the phone open the form, but the server has the last
    word: without a valid session the app goes to the login screen."""
    phone.context.clear_cookies()
    phone.goto(f"{server}/")
    phone.wait_for_selector("#login-name")
    assert phone.evaluate("() => localStorage.getItem('spese.lists')") is None


def test_a_duplicate_is_saved_with_a_warning(phone, api):
    add_expense(api, amount="45,20", merchant="Esselunga")
    save(phone, "45,20", "Esselunga", "Spesa alimentare")
    toast = phone.wait_for_selector(".toast-warning")
    assert "sembra un doppione" in toast.inner_text()
    assert "avevi già registrato la stessa spesa" in toast.inner_text()
    # Saved anyway; «Annulla» is there as always.
    assert len(api.get("/expenses").json()) == 2
    phone.click(".toast-warning .toast-action")
    phone.wait_for_selector(".toast:has-text('Spesa annullata.')")
    assert len(api.get("/expenses").json()) == 1


# --- Movimenti: search a page at a time ---------------------------------------------------


def test_search_shows_a_hundred_rows_and_then_the_others(phone, api, server):
    for number in range(130):
        add_expense(api, amount=f"{number + 1},00", merchant="Bar Prova")
    phone.goto(f"{server}/movimenti?cerca=bar%20prova")
    phone.wait_for_selector(".search-more")
    assert phone.locator(".row").count() == 100
    total = sum(range(1, 131))
    assert plain(phone.inner_text(".month-total-amount")) == f"{total:,}".replace(",", ".") + ",00 €"
    assert phone.inner_text(".month-total-count") == "130 spese"
    assert phone.inner_text(".search-more") == "Mostra altre 30 (100 di 130)"
    phone.click(".search-more")
    phone.locator(".row").nth(129).wait_for()
    assert phone.locator(".row").count() == 130
    assert phone.locator(".search-more").is_hidden()


# --- Riepilogo: incomes still expected ------------------------------------------------------


def test_summary_shows_the_salary_still_expected(phone, api, server):
    today = date.today()
    last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    api.post("/recurring-incomes", json={
        "amount": "2100", "category": "salary", "interval_months": 1, "next_due": last_day.isoformat(),
    }).raise_for_status()
    add_expense(api, amount="100")
    phone.goto(f"{server}/riepilogo")
    # 0.18.0: the ledger of the month
    expected = phone.wait_for_selector(".ledger-line.is-expected")
    assert "Entrate attese" in expected.inner_text()
    assert "Stipendio Fabio" in plain(expected.inner_text())
    assert "+ 2.100,00 €" in plain(expected.inner_text())
    final = phone.locator(".ledger-line.is-final")
    assert "A fine mese" in final.inner_text()
    assert "+ 2.000,00 €" in plain(final.inner_text())  # 2.100 expected - 100 spent
    assert "Differenza finora" in phone.locator(".ledger").inner_text()


# --- Impostazioni ---------------------------------------------------------------------------


def test_reorder_categories_changes_the_buttons_of_nuova_spesa(phone, server):
    phone.goto(f"{server}/impostazioni")
    phone.click("summary:has-text('Categorie')")
    phone.click("button:has-text('Cambia l’ordine')")
    phone.click(".order-step[aria-label='Sposta su «Salute»']")
    phone.wait_for_selector(".manage-item:nth-child(2):has-text('Salute')")
    phone.click("button:has-text('Fatto')")
    phone.goto(f"{server}/")
    phone.wait_for_selector(".cat")
    labels = phone.eval_on_selector_all(".cat", "(nodes) => nodes.map((node) => node.getAttribute('aria-label'))")
    assert labels[:3] == ["Spesa alimentare", "Salute", "Casa e utenze"]


def test_backup_download_and_the_files_for_claude(phone, api, server):
    add_expense(api, amount="20")
    api.post("/incomes", json={"amount": "1850", "category": "salary",
                               "income_date": date.today().isoformat()}).raise_for_status()
    phone.goto(f"{server}/impostazioni")
    phone.click("summary:has-text('Backup')")
    phone.wait_for_selector(".backup-last:has-text('Nessun backup scaricato finora.')")
    with phone.expect_download() as download:
        phone.click("button:has-text('Scarica backup')")
    assert download.value.suggested_filename.startswith("spese-backup-")
    phone.wait_for_selector(".backup-last:has-text('(Fabio)')")

    phone.click("summary:has-text('Esporta')")
    phone.click("label.radio:has-text('Tutto')")  # 0.15.0, «Per Claude» until 0.14.0
    names = []
    phone.on("download", lambda item: names.append(item.suggested_filename))
    phone.click(".export-actions button:has-text('Scarica')")
    toast = phone.wait_for_selector(".toast:has-text('2 file scaricati.')")
    month = date.today().strftime("%Y-%m")
    assert names == [f"spese_{month}.csv", f"entrate_{month}.csv"]
    toast.query_selector(".toast-action").click()  # «Copia testo»
    phone.wait_for_selector(".toast:has-text('Testo copiato')")
    text = phone.evaluate("() => navigator.clipboard.readText()")
    assert "1 spesa, totale 20,00 €" in text
    assert "Nessun articolo Vinted registrato." in text
    assert "Prima di tutto controlla di aver letto tutte le righe" in text


# --- Vinted -----------------------------------------------------------------------------------


def test_vinted_opens_on_the_first_filter_with_items(phone, api, server):
    api.post("/vinted/items", json={"title": "Giacca", "listed_on": date.today().isoformat()}).raise_for_status()
    phone.goto(f"{server}/vinted")
    selected = phone.wait_for_selector(".pill.is-selected")
    assert selected.get_attribute("aria-label") == "In vendita: 1"
    # A filter chosen in the address stays, even when empty.
    phone.goto(f"{server}/vinted?filtro=venduti")
    assert phone.wait_for_selector(".pill.is-selected").get_attribute("aria-label") == "Venduti: 0"


# --- every main screen at phone size ----------------------------------------------------------


@pytest.mark.parametrize("size", ["360", "320"])
def test_main_screens_fit_the_phone_without_errors(browser, server, api, size):
    add_expense(api, merchant="Un esercente dal nome piuttosto lungo", note="Una nota anche lei lunga")
    page = open_phone(browser, server, size)
    try:
        for route in ROUTES:
            page.goto(f"{server}{route}")
            page.wait_for_selector("#view .view-inner > *:not(.boot)")
            page.wait_for_timeout(300)
            wider = page.evaluate(
                "() => [...document.querySelectorAll('#view *')]"
                ".filter((node) => !node.closest('.chips-scroll, .filters'))"
                ".filter((node) => node.getBoundingClientRect().right > window.innerWidth + 1)"
                ".map((node) => node.className || node.tagName)")
            assert wider == [], f"{route} at {size} px: {wider}"
        assert unexpected_errors(page) == []
    finally:
        page.context.close()
