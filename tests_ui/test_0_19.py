"""0.19.0 on a phone-sized Chrome: the markdown of the Vinted items (F7).
The reminder in the list, the section «Ribasso» of an item with its
buttons, the plan chosen by hand and the plan read in Claude's answer."""

from __future__ import annotations

from datetime import date, timedelta

from tests_ui.conftest import unexpected_errors
from tests_ui.test_phone import plain


def ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def item(api, title, listed_ago, price, minimum):
    response = api.post("/vinted/items", json={"title": title, "listed_on": ago(listed_ago),
                                                "price": price, "min_price": minimum})
    response.raise_for_status()
    return response.json()["id"]


def section(page):
    return plain(page.locator(".md-card").inner_text())


def test_reminder_in_the_list_and_a_step_down(phone, api, server):
    jacket = item(api, "Giacca di jeans", 30, "35", "25")
    item(api, "Borsa a tracolla", 20, "45", "30")
    item(api, "Gonna", 3, "20", "15")  # not due yet
    phone.goto(f"{server}/vinted?filtro=tutti")
    banner = phone.wait_for_selector(".md-banner:not([hidden])")
    assert "2 articoli da ribassare" in banner.inner_text()
    assert phone.locator(".art-due").count() == 2
    banner.click()
    phone.wait_for_selector(".list-head:has-text('Da ribassare')")
    assert "filtro=ribassare" in phone.url
    assert phone.locator(".card.rows .art-row").count() == 2
    assert phone.locator(".md-banner").is_hidden()

    phone.goto(f"{server}/vinted/articolo/{jacket}")
    phone.wait_for_selector(".md-card")
    assert phone.locator(".status.is-due").inner_text() == "Da ribassare"
    text = section(phone)
    assert "−10% ogni 14 giorni" in text and "Piano base · minimo 25,00 €" in text
    assert "È ora di ribassare: 35,00 € → 31,50 €" in text
    assert "Poi: 28,00 € · 25,00 € (minimo)" in text
    phone.click("button:has-text('Ribassa a 31,50 €')")
    phone.wait_for_selector(".md-card:has-text('Prossimo ribasso')")
    assert "31,50" in plain(phone.locator(".hero-price").inner_text())
    expected = (date.today() + timedelta(days=14))
    assert f"Prossimo ribasso il {expected.day} " in section(phone)
    assert phone.locator(".status.is-due").count() == 0
    assert unexpected_errors(phone) == []


def test_skip_and_at_the_minimum(phone, api, server):
    bag = item(api, "Borsa", 20, "45", "30")
    phone.goto(f"{server}/vinted/articolo/{bag}")
    phone.click("button:has-text('Salta 14 giorni')")
    phone.wait_for_selector(".md-card:has-text('Prossimo ribasso')")
    assert "45,00" in plain(phone.locator(".hero-price").inner_text())

    skirt = item(api, "Gonna", 20, "15", "15")
    phone.goto(f"{server}/vinted/articolo/{skirt}")
    phone.wait_for_selector(".md-due")
    text = section(phone)
    assert "Al minimo da 20 giorni, ancora invenduto" in text
    for label in ("Rivaluta con Claude", "Ritira dalla vendita", "Lascia così"):
        assert phone.locator(f".md-card button:has-text('{label}')").count() == 1
    phone.click(".md-card button:has-text('Lascia così')")
    phone.wait_for_selector(".md-card:has-text('Lasciato al minimo')")
    assert phone.locator(".md-due").count() == 0

    # «Rivaluta con Claude» opens the steps of the ad.
    scarf = item(api, "Sciarpa", 20, "8", "8")
    phone.goto(f"{server}/vinted/articolo/{scarf}")
    phone.click(".md-card button:has-text('Rivaluta con Claude')")
    phone.wait_for_selector("text=Chiedi a Claude")
    assert unexpected_errors(phone) == []


def test_plan_by_hand_and_from_claude(phone, api, server):
    dress = item(api, "Abito", 4, "15", "12")
    phone.goto(f"{server}/vinted/articolo/{dress}")
    phone.click(".md-card button:has-text('Cambia')")
    phone.click(".dialog-option:has-text('Scrivo io')")
    phone.click(".md-unit button:has-text('In euro')")
    phone.fill("#markdown-amount", "2")
    phone.fill("#markdown-days", "7")
    phone.click(".dialog button:has-text('Salva')")
    phone.wait_for_selector(".md-card:has-text('−2 € ogni 7 giorni')")
    assert "Scelto da te" in section(phone)

    answer = ("TITOLO: Abito da cocktail\nDESCRIZIONE:\nAbito corto a paillettes.\nPREZZO: 15\nMINIMO: 12\n"
              "RIBASSO: 1 € ogni 10 giorni\nVERIFICA: niente")
    phone.evaluate("(text) => navigator.clipboard.writeText(text)", answer)
    phone.goto(f"{server}/vinted/articolo/{dress}/annuncio")
    phone.click("button:has-text('Incolla risposta di Claude')")
    hint = phone.wait_for_selector(".md-hint:not([hidden])")
    assert hint.inner_text() == "Ribasso: −1 € ogni 10 giorni (proposto da Claude)."
    phone.click("button:has-text('Salva annuncio')")
    phone.wait_for_selector(".md-card:has-text('−1 € ogni 10 giorni')")
    assert "Proposto da Claude" in section(phone)

    # Back to the base plan from the sheet.
    phone.click(".md-card button:has-text('Cambia')")
    phone.click(".dialog-option:has-text('Piano base')")
    phone.wait_for_selector(".md-card:has-text('−10% ogni 14 giorni')")
    assert unexpected_errors(phone) == []
