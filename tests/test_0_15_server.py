"""0.15.0: category icons and the text of every export (Scarica e Condividi)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from app.category_icons import ALL_ICONS, CHOOSABLE_ICONS, DEFAULT_ICON, INCOME_CATEGORY_ICONS
from app.config import get_settings
from app.schemas import INCOME_CATEGORIES
from tests.conftest import make_expense, strip_category_icons
from tests.test_incomes import make_income
from tests.test_vinted import bought, make_item, sell

API = "/api/v1"
ICONS_JS = Path(__file__).parent.parent / "app" / "static" / "js" / "category-icons.js"


# --- icons ------------------------------------------------------------------------------


def icons_of(client):
    return {c["name"]: c["icon"] for c in client.get(f"{API}/categories?include_inactive=true").json()}


def test_initial_categories_have_their_icons(client):
    assert icons_of(client) == {
        "Spesa alimentare": "shopping-cart",
        "Casa e utenze": "home-bolt",
        "Salute": "first-aid-kit",
        "Auto e trasporti": "car",
        "Ristoranti e bar": "tools-kitchen-2",
        "Abbigliamento": "shirt",
        "Svago": "ticket",
        "Abbonamenti": "repeat",
        "Regali": "gift",
        "Varie": "dots",
        "Vinted": "hanger",
    }


def test_list_of_icons(client, anon):
    body = client.get(f"{API}/categories/icons").json()
    assert body == {"icons": list(CHOOSABLE_ICONS), "default": DEFAULT_ICON}
    assert len(set(body["icons"])) == len(body["icons"])
    assert anon.get(f"{API}/categories/icons").status_code == 401


def test_create_with_and_without_icon(client):
    with_icon = client.post(f"{API}/categories", json={"name": "Animali", "icon": "paw"})
    assert with_icon.status_code == 201, with_icon.text
    assert with_icon.json()["icon"] == "paw"
    without = client.post(f"{API}/categories", json={"name": "Scuola"}).json()
    assert without["icon"] == DEFAULT_ICON  # none chosen: the default one
    wrong = client.post(f"{API}/categories", json={"name": "Bici", "icon": "unicorn"})
    assert wrong.status_code == 422
    assert "Icona non disponibile" in wrong.json()["detail"]
    assert "Bici" not in icons_of(client)


def test_change_the_icon(client, categories):
    category_id = categories["Svago"]
    changed = client.patch(f"{API}/categories/{category_id}", json={"icon": "movie"})
    assert changed.status_code == 200 and changed.json()["icon"] == "movie"
    renamed = client.patch(f"{API}/categories/{category_id}", json={"name": "Tempo libero"}).json()
    assert renamed["icon"] == "movie"  # renaming keeps the icon
    assert client.patch(f"{API}/categories/{category_id}", json={"icon": "nope"}).status_code == 422
    assert icons_of(client)["Tempo libero"] == "movie"
    # The Vinted category's icon can change too, like its name.
    vinted = categories["Vinted"]
    assert client.patch(f"{API}/categories/{vinted}", json={"icon": "tag"}).json()["icon"] == "tag"


def test_income_categories_have_fixed_icons(client):
    listed = client.get(f"{API}/incomes/categories").json()
    assert [c["code"] for c in listed] == list(INCOME_CATEGORIES)
    assert {c["code"]: c["icon"] for c in listed} == INCOME_CATEGORY_ICONS


def test_every_icon_has_its_drawing():
    """The names travel through the API; the drawings are in the interface."""
    text = ICONS_JS.read_text(encoding="utf-8")
    drawn = set(re.findall(r"^  '([a-z0-9-]+)': '<", text, flags=re.MULTILINE))
    assert ALL_ICONS <= drawn, sorted(ALL_ICONS - drawn)
    assert DEFAULT_ICON in drawn


def test_backup_of_014_gets_the_icons(client, categories, tmp_path):
    client.patch(f"{API}/categories/{categories['Varie']}", json={"name": "Altro ancora"})
    client.post(f"{API}/categories", json={"name": "Animali", "icon": "paw"})
    backup = client.get(f"{API}/backup").content
    old = tmp_path / "schema8.db"
    old.write_bytes(backup)
    conn = sqlite3.connect(old)
    strip_category_icons(conn)
    conn.execute("PRAGMA user_version = 8")
    conn.commit()
    conn.close()
    response = client.post(f"{API}/restore", content=old.read_bytes(),
                           headers={"Content-Type": "application/octet-stream"})
    assert response.status_code == 200, response.text
    icons = icons_of(client)
    assert icons["Spesa alimentare"] == "shopping-cart" and icons["Vinted"] == "hanger"
    # Renamed or created by hand: no icon known by its name, the default one.
    assert icons["Altro ancora"] == DEFAULT_ICON
    assert icons["Animali"] == DEFAULT_ICON
    live = sqlite3.connect(get_settings().db_path)
    try:
        assert live.execute("PRAGMA user_version").fetchone()[0] == 10
        assert live.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        live.close()


# --- the text of every export --------------------------------------------------------------


def brief(client, **params):
    response = client.get(f"{API}/export/brief", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_brief_of_the_expenses_alone(client, categories):
    make_expense(client, categories, amount="40", expense_date="2026-11-10")
    make_income(client, amount="1000", income_date="2026-11-10")
    body = brief(client, month="2026-11", what="expenses")
    assert [f["name"] for f in body["files"]] == ["spese_2026-11.csv"]
    text = body["text"]
    assert "spese_2026-11.csv: 1 spesa, totale 40,00 €." in text
    assert "entrat" not in text.split("Come leggere")[0]  # incomes not mentioned above
    assert "Entrate meno spese" not in text
    assert "Articoli Vinted" not in text


def test_brief_of_the_incomes_alone(client, categories):
    make_expense(client, categories, amount="40", expense_date="2026-11-10")
    make_income(client, amount="160", category="meal_voucher", income_date="2026-11-10")
    body = brief(client, month="2026-11", what="incomes")
    assert [f["name"] for f in body["files"]] == ["entrate_2026-11.csv"]
    assert "1 entrata, totale 160,00 €, di cui 160,00 € in buoni pasto." in body["text"]
    assert "spesa" not in body["text"].split("Come leggere")[0]


def test_brief_of_the_vinted_items(client):
    first = make_item(client, title="Borsa", purchase=bought("12,00"))
    sell(client, first["id"], "25,00")
    make_item(client, title="Giacca", purchase=bought("8,00"))
    body = brief(client, what="vinted")
    assert body["files"] == [{"name": "vinted_articoli.csv", "url": "/api/v1/export/vinted.csv?format=standard"}]
    text = body["text"]
    assert "tutti gli articoli Vinted registrati" in text
    assert "vinted_articoli.csv: 2 articoli Vinted" in text
    assert "1 da pubblicare, 1 venduto" in text
    assert "Pagati 20,00 €, venduti 25,00 €, guadagno sui venduti +13,00 €." in text
    assert "Articoli Vinted: guadagno" in text
    assert client.get(body["files"][0]["url"]).status_code == 200


def test_brief_of_everything(client, categories):
    make_expense(client, categories, amount="40", expense_date="2026-11-10")
    make_income(client, amount="100", income_date="2026-11-10")
    make_item(client, title="Borsa", purchase=bought("12,00"))
    body = brief(client, month="2026-11")  # "all" is the default
    assert [f["name"] for f in body["files"]] == [
        "spese_2026-11.csv", "entrate_2026-11.csv", "vinted_articoli.csv",
    ]
    assert body == brief(client, month="2026-11", what="all")
    assert "Entrate meno spese: +48,00 €." in body["text"]  # 100 − 40 − 12 of the item
    for file in body["files"]:
        assert client.get(file["url"]).status_code == 200


def test_brief_of_everything_without_vinted_items(client, categories):
    make_expense(client, categories, amount="40", expense_date="2026-11-10")
    body = brief(client, month="2026-11", what="all")
    assert [f["name"] for f in body["files"]] == ["spese_2026-11.csv"]
    assert "Nessun articolo Vinted registrato." in body["text"]
    assert "Nessuna entrata registrata nel periodo." in body["text"]


def test_brief_in_the_excel_format(client, categories):
    make_expense(client, categories, amount="40", expense_date="2026-11-10")
    make_item(client, title="Borsa", purchase=bought("12,00"))
    body = brief(client, month="2026-11", what="all", format="excel_it")
    assert body["files"] == [
        {"name": "spese_2026-11_excel.csv", "url": "/api/v1/export.csv?month=2026-11&format=excel_it"},
        {"name": "vinted_articoli_excel.csv", "url": "/api/v1/export/vinted.csv?format=excel_it"},
    ]
    assert "Formato «Excel italiano»: separatore punto e virgola, virgola decimale." in body["text"]
    response = client.get(body["files"][0]["url"])
    assert response.content.startswith(b"\xef\xbb\xbf")  # the Excel file, with its BOM


def test_brief_rejects_an_unknown_kind(client):
    assert client.get(f"{API}/export/brief", params={"what": "backup"}).status_code == 422
    assert client.get(f"{API}/export/brief", params={"format": "xlsx"}).status_code == 422
