"""0.15.0 on a phone-sized Chrome: categories as icons (name in the label,
in a bubble and in the Save button; the merchant chosen coloured), the icon
picker of Impostazioni, «Scarica» and «Condividi» of the exports."""

from __future__ import annotations

from datetime import date

from tests_ui.conftest import open_phone, unexpected_errors
from tests_ui.test_phone import add_expense, plain

# navigator.share as on Android, recording what it receives: headless Chrome
# on Linux has none.
FAKE_SHARE = """
window.__shared = [];
Object.defineProperty(navigator, 'canShare', { configurable: true, value: (data) => Boolean(data && data.files) });
Object.defineProperty(navigator, 'share', { configurable: true, value: async (data) => {
  const files = [];
  for (const file of data.files || []) files.push({ name: file.name, type: file.type, text: await file.text() });
  window.__shared.push({ files, text: data.text || null });
} });
"""


def categories_of(phone):
    return phone.eval_on_selector_all(
        ".cat-grid-icons .cat", "(nodes) => nodes.map((node) => node.getAttribute('aria-label'))")


def test_categories_are_icons_four_to_a_row(phone):
    assert len(categories_of(phone)) == 11
    assert phone.inner_text(".cat") == ""  # no text: the name is the label
    tops = phone.eval_on_selector_all(".cat-grid-icons .cat", "(nodes) => nodes.map((n) => n.getBoundingClientRect().top)")
    assert len(set(tops[:4])) == 1 and tops[4] > tops[0]  # four in the first row
    assert phone.inner_text(".btn-save") == "Salva spesa"
    assert phone.inner_text("#category-label") == "Categoria"


def test_the_name_is_in_the_label_the_bubble_and_the_save_button(phone):
    phone.click(".cat[aria-label='Ristoranti e bar']")
    assert phone.inner_text("#category-label") == "Categoria · Ristoranti e bar"
    assert phone.inner_text(".cat.is-selected .cat-bubble") == "Ristoranti e bar"
    assert phone.inner_text(".btn-save") == "Salva in Ristoranti e bar"
    phone.wait_for_selector(".cat-bubble", state="detached", timeout=3000)  # gone after 1.5 s
    assert phone.inner_text("#category-label") == "Categoria · Ristoranti e bar"  # the label stays
    # Saved: back to no category, and to «Salva spesa».
    phone.fill("#expense-amount", "4,50")
    phone.click(".btn-save")
    phone.wait_for_selector(".toast-success")
    assert phone.inner_text(".btn-save") == "Salva spesa"
    assert phone.inner_text("#category-label") == "Categoria"
    assert unexpected_errors(phone) == []


def test_a_known_merchant_picks_its_category_and_stays_coloured(phone, api, server):
    categories = {c["name"]: c["id"] for c in api.get("/categories").json()}
    add_expense(api, merchant="Bar Centrale", category_id=categories["Ristoranti e bar"])
    phone.goto(f"{server}/")
    phone.click(".chips-scroll .chip:has-text('Bar Centrale')")
    chosen = phone.wait_for_selector(".chips-scroll .chip.is-selected")
    assert chosen.inner_text() == "Bar Centrale"
    assert phone.eval_on_selector(".chips-scroll .chip", "(node) => node.classList.contains('is-selected')")
    assert phone.get_attribute(".cat.is-selected", "aria-label") == "Ristoranti e bar"
    assert phone.inner_text(".cat.is-selected .cat-bubble") == "Ristoranti e bar"  # shown, not hidden
    assert phone.inner_text(".btn-save") == "Salva in Ristoranti e bar"
    # Tapped again: the merchant is cleared, the category chosen stays.
    chosen.click()
    assert phone.input_value("#expense-merchant") == ""
    assert phone.locator(".chips-scroll .chip.is-selected").count() == 0
    assert phone.get_attribute(".cat.is-selected", "aria-label") == "Ristoranti e bar"


def test_typing_the_full_name_colours_the_merchant_too(phone, api, server):
    add_expense(api, merchant="Esselunga")
    phone.goto(f"{server}/")
    phone.fill("#expense-merchant", "esselunga")
    assert phone.inner_text(".chips-scroll .chip.is-selected") == "Esselunga"
    assert phone.inner_text(".btn-save") == "Salva in Spesa alimentare"


def test_new_category_with_its_icon_reaches_nuova_spesa(phone, server):
    phone.goto(f"{server}/impostazioni")
    phone.click("summary:has-text('Categorie')")
    phone.fill("input[aria-label='Nome della nuova categoria']", "Animali")
    phone.click("button:has-text('Aggiungi')")
    phone.wait_for_selector("dialog .icon-picker")
    # Without an icon the window says so.
    phone.click("dialog button[type=submit]")
    assert "Scegli un’icona" in phone.inner_text("dialog .field-error")
    phone.click("dialog .icon-choice[aria-label='zampa']")
    phone.click("dialog button[type=submit]")
    phone.wait_for_selector(".toast:has-text('Categoria aggiunta.')")
    # Change the icon of an existing one, name unchanged.
    phone.click(".manage-item:has-text('Svago') button:has-text('Modifica')")
    assert phone.get_attribute("dialog .icon-choice.is-selected", "aria-label") == "biglietto"
    phone.click("dialog .icon-choice[aria-label='cinema']")
    phone.click("dialog button[type=submit]")
    phone.wait_for_selector(".toast:has-text('Categoria modificata.')")
    phone.goto(f"{server}/")
    assert categories_of(phone)[-1] == "Animali"
    assert phone.eval_on_selector(".cat[aria-label='Animali'] svg", "(svg) => svg.innerHTML.length") > 50
    phone.click(".cat[aria-label='Animali']")
    assert phone.inner_text(".btn-save") == "Salva in Animali"
    assert unexpected_errors(phone) == []


def test_new_income_with_icons(phone, server):
    phone.goto(f"{server}/entrate/nuova")
    phone.wait_for_selector("#income-amount")
    assert len(categories_of(phone)) == 7
    assert phone.inner_text(".btn-save") == "Salva entrata"
    phone.click(".cat[aria-label='Stipendio']")
    assert phone.inner_text("#income-category-label") == "Categoria · Stipendio"
    assert phone.inner_text(".btn-save") == "Salva in Stipendio"
    phone.fill("#income-amount", "1850,00")
    phone.click(".btn-save")
    assert plain(phone.wait_for_selector(".toast-success").inner_text()).startswith("Entrata salvata: 1.850,00 €")


def test_share_copies_the_text_and_shares_the_files(browser, server, api):
    add_expense(api, amount="20")
    api.post("/vinted/items", json={"title": "Giacca", "listed_on": date.today().isoformat()}).raise_for_status()
    page = open_phone(browser, server)
    page.context.add_init_script(FAKE_SHARE)
    try:
        page.goto(f"{server}/impostazioni")
        page.click("summary:has-text('Esporta')")
        share = page.locator(".export-actions button:has-text('Condividi')")
        assert share.is_visible()
        # Articoli Vinted: no period, one file.
        page.click("label.radio:has-text('Articoli Vinted')")
        share.click()
        page.wait_for_function("() => window.__shared.length === 1")
        shared = page.evaluate("() => window.__shared[0]")
        assert [f["name"] for f in shared["files"]] == ["vinted_articoli.csv"]
        assert shared["files"][0]["type"] == "text/csv" and "Giacca" in shared["files"][0]["text"]
        text = page.evaluate("() => navigator.clipboard.readText()")
        assert "vinted_articoli.csv: 1 articolo Vinted" in text
        assert page.locator("#toasts.toasts-top .toast:has-text('Testo copiato')").count() == 1
        # Tutto, in the Excel format: the files of both kinds.
        page.click("label.radio:has-text('Tutto')")
        page.click("label.radio:has-text('Excel italiano')")
        share.click()
        page.wait_for_function("() => window.__shared.length === 2")
        names = page.evaluate("() => window.__shared[1].files.map((f) => f.name)")
        month = date.today().strftime("%Y-%m")
        assert names == [f"spese_{month}_excel.csv", "vinted_articoli_excel.csv"]
        assert "Formato «Excel italiano»" in page.evaluate("() => navigator.clipboard.readText()")
        # Nothing to export: said, nothing shared.
        page.click("label.radio:has-text('Entrate')")
        share.click()
        page.wait_for_selector(".toast-error:has-text('Nel periodo non ci sono entrate.')")
        assert page.evaluate("() => window.__shared.length") == 2
        assert unexpected_errors(page) == []
    finally:
        page.context.close()


def test_without_share_only_download(phone, server):
    """Plain HTTP or a computer: no «Condividi», a line says where it is."""
    phone.goto(f"{server}/impostazioni")
    phone.click("summary:has-text('Esporta')")
    if phone.evaluate("() => Boolean(navigator.share)"):
        return  # this Chrome shares: covered above
    assert phone.locator(".export-actions button:has-text('Condividi')").is_hidden()
    assert "dall’indirizzo di Tailscale" in phone.inner_text(".export-share-hint")


def test_deactivate_from_the_window_of_the_category(phone, api, server):
    phone.goto(f"{server}/impostazioni")
    phone.click("summary:has-text('Categorie')")
    assert phone.locator(".manage-item:has-text('Vinted') button").all_inner_texts() == ["Modifica"]
    phone.click(".manage-item:has-text('Vinted') button:has-text('Modifica')")
    assert phone.locator("dialog .category-toggle").count() == 0  # the Vinted one stays active
    phone.click("dialog button:has-text('Annulla')")
    phone.click(".manage-item:has-text('Regali') button:has-text('Modifica')")
    assert phone.evaluate("() => document.activeElement.tagName") == "H2"  # no keyboard over the icons
    phone.click("dialog .category-toggle")
    phone.click("dialog button:has-text('Disattiva')")
    phone.wait_for_selector(".manage-item:has-text('Regali') .tag:has-text('disattivata')")
    regali = next(c for c in api.get("/categories?include_inactive=true").json() if c["name"] == "Regali")
    assert regali["is_active"] is False
    phone.goto(f"{server}/")
    assert "Regali" not in categories_of(phone)
