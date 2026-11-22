"""Vinted section (0.8.0): items, purchases and sales linked to expenses and
incomes, photos, summary, CSV, and the update of a database that already had
a "Vinted" category created by hand."""

from __future__ import annotations

import base64
import csv
import io
import sqlite3
from datetime import date

from fastapi.testclient import TestClient

from tests.conftest import PINNED_TODAY, make_expense, strip_vinted_schema

API = "/api/v1"
VINTED_CSV_HEADER = [
    "articolo", "stato", "data_acquisto", "prezzo_acquisto", "data_vendita", "prezzo_vendita",
    "guadagno", "giorni_in_vendita", "nota", "inserito_da", "creato_il",
]
# The server only checks the JPEG signature: no image library needed here.
JPEG = b"\xff\xd8\xff\xe0" + bytes(range(256)) * 4
THUMB = b"\xff\xd8\xff\xe0" + bytes(range(64))


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def vinted_category(client) -> dict:
    found = [c for c in client.get(f"{API}/categories?include_inactive=true").json() if c["system_key"]]
    assert len(found) == 1
    return found[0]


def make_item(client, **body):
    payload = {"title": "Borsa a tracolla"}
    payload.update(body)
    response = client.post(f"{API}/vinted/items", json=payload)
    assert response.status_code in (200, 201), response.text
    return response.json()


def bought(amount="12,00", day="2026-11-02", **extra):
    return {"amount": amount, "expense_date": day, **extra}


def sell(client, item_id, amount="25,00", day="2026-11-18", **extra):
    response = client.post(
        f"{API}/vinted/items/{item_id}/sale", json={"amount": amount, "income_date": day, **extra}
    )
    assert response.status_code == 200, response.text
    return response.json()


def users_of(client):
    return {u["display_name"]: u["id"] for u in client.get(f"{API}/users").json()}


# --- the category ----------------------------------------------------------------


def test_vinted_category_can_be_renamed_not_deactivated_or_deleted(client):
    vinted = vinted_category(client)
    assert vinted["name"] == "Vinted" and vinted["system_key"] == "vinted" and vinted["is_active"]
    others = [c for c in client.get(f"{API}/categories").json() if c["id"] != vinted["id"]]
    assert all(c["system_key"] is None for c in others)

    response = client.patch(f"{API}/categories/{vinted['id']}", json={"is_active": False})
    assert response.status_code == 409
    assert "sezione Vinted" in response.json()["detail"]
    assert client.delete(f"{API}/categories/{vinted['id']}").status_code == 409

    renamed = client.patch(f"{API}/categories/{vinted['id']}", json={"name": "Vinted rivendita"})
    assert renamed.status_code == 200
    assert renamed.json()["system_key"] == "vinted"
    # The section follows the category, whatever its name.
    item = make_item(client, purchase=bought())
    expense = client.get(f"{API}/expenses/{item['purchase']['expense_id']}").json()
    assert expense["category_name"] == "Vinted rivendita"


def test_update_adopts_the_category_created_by_hand(client, categories, tmp_path):
    """Fabio and Nastia created "Vinted" by hand before 0.8.0: the update keeps
    it, with its expenses and its place, and does not add a second one."""
    vinted_id = categories["Vinted"]
    make_expense(client, categories, category_id=vinted_id, merchant="Vinted", amount="8,00")
    old = tmp_path / "schema4.db"
    old.write_bytes(client.get(f"{API}/backup").content)
    conn = sqlite3.connect(old)
    strip_vinted_schema(conn)
    # As made by hand: other capitals, another place, even deactivated.
    conn.execute(
        "UPDATE categories SET name = 'VINTED', is_active = 0, sort_order = 55 WHERE id = ?",
        (vinted_id,),
    )
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
    conn.close()

    assert client.post(f"{API}/restore", content=old.read_bytes()).status_code == 200
    vinted = vinted_category(client)
    assert vinted["id"] == vinted_id
    assert (vinted["name"], vinted["is_active"], vinted["sort_order"]) == ("VINTED", True, 55)
    assert vinted["expense_count"] == 1
    names = [c["name"].casefold() for c in client.get(f"{API}/categories?include_inactive=true").json()]
    assert names.count("vinted") == 1
    # Its expense waits to be linked to an item.
    waiting = client.get(f"{API}/vinted/unlinked-expenses").json()
    assert [e["amount_cents"] for e in waiting] == [800]


def test_update_adds_the_category_when_missing(client, tmp_path):
    old = tmp_path / "schema4.db"
    old.write_bytes(client.get(f"{API}/backup").content)
    conn = sqlite3.connect(old)
    strip_vinted_schema(conn)
    conn.execute("DELETE FROM categories WHERE name_key = 'vinted'")
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
    conn.close()

    assert client.post(f"{API}/restore", content=old.read_bytes()).status_code == 200
    vinted = vinted_category(client)
    assert (vinted["name"], vinted["is_active"], vinted["sort_order"]) == ("Vinted", True, 110)
    assert [c["name"] for c in client.get(f"{API}/categories").json()][-1] == "Vinted"


def test_merchant_suggestion_skips_the_vinted_category(client, categories):
    vinted_id = categories["Vinted"]
    make_expense(client, categories, merchant="Vinted", category_id=categories["Abbigliamento"],
                 expense_date="2026-11-01")
    make_expense(client, categories, merchant="Vinted", category_id=vinted_id, expense_date="2026-11-05")
    merchant = next(m for m in client.get(f"{API}/merchants").json() if m["name"] == "Vinted")
    # The newest expense is in Vinted, but a purchase for the house must not start there.
    assert merchant["last_category_id"] == categories["Abbigliamento"]

    make_expense(client, categories, merchant="Mercatino", category_id=vinted_id)
    merchant = next(m for m in client.get(f"{API}/merchants").json() if m["name"] == "Mercatino")
    assert merchant["last_category_id"] is None


# --- items, purchases ------------------------------------------------------------


def test_item_bought_to_resell(client, categories):
    item = make_item(client, title="  Borsa   a tracolla ", note=" pelle ", purchase=bought())
    assert item["title"] == "Borsa a tracolla"
    assert item["note"] == "pelle"
    assert item["status"] == "listed"
    assert item["listed_on"] == "2026-11-02"  # on sale since the purchase
    assert item["photo"] is None and item["sale"] is None and item["gain_cents"] is None
    purchase = item["purchase"]
    assert purchase["amount_cents"] == 1200
    assert purchase["merchant_name"] == "Vinted"  # default merchant
    assert (purchase["paid_by_name"], purchase["payment_method"]) == ("Fabio", "card")
    assert item["created_by_name"] == "Fabio"

    # The purchase is a normal expense of the Vinted category, linked to the item.
    expense = client.get(f"{API}/expenses/{purchase['expense_id']}").json()
    assert expense["category_id"] == categories["Vinted"]
    assert (expense["vinted_item_id"], expense["vinted_item_title"]) == (item["id"], "Borsa a tracolla")
    listed = client.get(f"{API}/expenses?month=2026-11").json()
    assert [e["vinted_item_id"] for e in listed] == [item["id"]]
    assert client.get(f"{API}/vinted/unlinked-expenses").json() == []
    assert client.get(f"{API}/vinted/items/{item['id']}").json() == item


def test_purchase_details_and_validation(client):
    users = users_of(client)
    item = make_item(client, purchase=bought(
        "18,50", "2026-11-12", merchant="Mercatino di via Roma", paid_by_user_id=users["Nastia"],
        payment_method="other"))
    purchase = item["purchase"]
    assert (purchase["merchant_name"], purchase["paid_by_name"], purchase["payment_method"]) == (
        "Mercatino di via Roma", "Nastia", "other")
    no_merchant = make_item(client, purchase=bought(merchant=None))
    assert no_merchant["purchase"]["merchant_name"] is None

    def post(**body):
        return client.post(f"{API}/vinted/items", json={"title": "Felpa", **body})

    assert post(title="   ").status_code == 422
    assert post(title="").status_code == 422
    assert post(purchase={"expense_date": "2026-11-02"}).json()["detail"] == "Inserisci il prezzo pagato."
    assert post(purchase={"amount": "4"}).json()["detail"] == "Inserisci la data dell'acquisto."
    assert post(purchase=bought("abc")).status_code == 422
    assert post(purchase=bought(day="2027-08-01")).status_code == 422  # future
    assert post(listed_on="2027-08-01").status_code == 422
    assert post(purchase=bought(paid_by_user_id=999)).status_code == 422
    # Nothing half-saved by the refused requests.
    assert len(client.get(f"{API}/vinted/items").json()) == 2
    assert len(client.get(f"{API}/expenses").json()) == 2


def test_item_already_at_home(client):
    item = make_item(client, title="Giacca blazer bambini")
    assert item["purchase"] is None
    assert item["listed_on"] == PINNED_TODAY.isoformat()
    dated = make_item(client, title="Zaino", listed_on="2026-10-14")
    assert dated["listed_on"] == "2026-10-14"
    assert client.get(f"{API}/expenses").json() == []


def test_link_a_purchase_recorded_from_new_expense(client, categories):
    expense = make_expense(client, categories, category_id=categories["Vinted"], merchant="Vinted",
                           amount="14", expense_date="2026-10-30")
    other = make_expense(client, categories)  # Spesa alimentare
    waiting = client.get(f"{API}/vinted/unlinked-expenses").json()
    assert [e["id"] for e in waiting] == [expense["id"]]

    item = make_item(client, title="Cappotto", purchase={"expense_id": expense["id"]})
    assert item["purchase"]["expense_id"] == expense["id"]
    assert item["purchase"]["amount_cents"] == 1400
    assert item["listed_on"] == "2026-10-30"
    assert len(client.get(f"{API}/expenses").json()) == 2  # linked, not copied

    again = client.post(f"{API}/vinted/items", json={"title": "Altro", "purchase": {"expense_id": expense["id"]}})
    assert again.status_code == 409
    wrong = client.post(f"{API}/vinted/items", json={"title": "Altro", "purchase": {"expense_id": other["id"]}})
    assert wrong.status_code == 422
    assert "categoria Vinted" in wrong.json()["detail"]
    missing = client.post(f"{API}/vinted/items", json={"title": "Altro", "purchase": {"expense_id": 999}})
    assert missing.status_code == 422

    # An item added without purchase can get one later.
    later = make_expense(client, categories, category_id=categories["Vinted"], amount="3")
    own = make_item(client, title="Pantaloni")
    linked = client.post(f"{API}/vinted/items/{own['id']}/purchase", json={"expense_id": later["id"]})
    assert linked.status_code == 200
    assert linked.json()["purchase"]["amount_cents"] == 300
    new = client.post(f"{API}/vinted/items/{own['id']}/purchase", json=bought())
    assert new.status_code == 409


def test_create_is_idempotent(client):
    body = {"title": "Borsa", "purchase": bought(), "client_uuid": "item-0001-retry"}
    first = client.post(f"{API}/vinted/items", json=body)
    second = client.post(f"{API}/vinted/items", json=body)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json() == second.json()
    assert len(client.get(f"{API}/vinted/items").json()) == 1
    assert len(client.get(f"{API}/expenses").json()) == 1


# --- sales -------------------------------------------------------------------------


def test_sale_of_a_resold_item(client):
    item = make_item(client, purchase=bought())
    sold = sell(client, item["id"])
    assert sold["status"] == "sold"
    assert sold["sale"]["amount_cents"] == 2500
    assert sold["sale"]["income_date"] == "2026-11-18"
    assert sold["sale"]["received_by_name"] == "Fabio"
    assert sold["gain_cents"] == 1300

    income = client.get(f"{API}/incomes/{sold['sale']['income_id']}").json()
    assert (income["category"], income["category_name"]) == ("vinted", "Vinted")
    assert (income["vinted_item_id"], income["vinted_item_title"]) == (item["id"], "Borsa a tracolla")

    again = client.post(f"{API}/vinted/items/{item['id']}/sale", json={"amount": "30", "income_date": "2026-11-19"})
    assert again.status_code == 409
    assert len(client.get(f"{API}/incomes").json()) == 1


def test_sale_of_something_already_at_home_and_by_the_other_person(client):
    users = users_of(client)
    item = make_item(client, title="Giacca", listed_on="2026-11-01")
    sold = sell(client, item["id"], "15", "2026-11-20", received_by_user_id=users["Nastia"])
    assert sold["gain_cents"] == 1500  # costs nothing: the whole price
    assert sold["sale"]["received_by_name"] == "Nastia"


def test_sale_retry_and_validation(client):
    item = make_item(client, purchase=bought())
    body = {"amount": "25", "income_date": "2026-11-18", "client_uuid": "sale-0001-retry"}
    first = client.post(f"{API}/vinted/items/{item['id']}/sale", json=body)
    second = client.post(f"{API}/vinted/items/{item['id']}/sale", json=body)
    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json() == second.json()
    assert len(client.get(f"{API}/incomes").json()) == 1

    other = make_item(client, title="Felpa")
    for body in ({"income_date": "2026-11-18"}, {"amount": "0", "income_date": "2026-11-18"},
                 {"amount": "9", "income_date": "2027-08-01"}):
        assert client.post(f"{API}/vinted/items/{other['id']}/sale", json=body).status_code == 422
    assert client.post(f"{API}/vinted/items/999/sale", json={"amount": "9"}).status_code == 404
    # Without a date the sale is today.
    today_sale = client.post(f"{API}/vinted/items/{other['id']}/sale", json={"amount": "9"}).json()
    assert today_sale["sale"]["income_date"] == PINNED_TODAY.isoformat()


def test_link_a_sale_recorded_from_new_income(client):
    def income(category, amount="20"):
        response = client.post(f"{API}/incomes", json={
            "amount": amount, "category": category, "income_date": "2026-11-10"})
        assert response.status_code == 201
        return response.json()

    old_sale = income("sale")        # recorded in "Vendite" before 0.8.0
    quick = income("vinted", "9")   # recorded from "Nuova entrata"
    salary = income("salary", "1850")
    waiting = client.get(f"{API}/vinted/unlinked-incomes").json()
    assert {i["id"] for i in waiting} == {old_sale["id"], quick["id"]}

    first = make_item(client, title="Tuta")
    linked = client.post(f"{API}/vinted/items/{first['id']}/sale", json={"income_id": old_sale["id"]})
    assert linked.status_code == 200
    assert linked.json()["sale"]["amount_cents"] == 2000
    # "Vendite" became "Vinted": the sale now counts in the section.
    assert client.get(f"{API}/incomes/{old_sale['id']}").json()["category"] == "vinted"

    second = make_item(client, title="Scarpe")
    assert client.post(f"{API}/vinted/items/{second['id']}/sale",
                       json={"income_id": old_sale["id"]}).status_code == 409
    assert client.post(f"{API}/vinted/items/{second['id']}/sale",
                       json={"income_id": salary["id"]}).status_code == 422
    assert client.post(f"{API}/vinted/items/{second['id']}/sale",
                       json={"income_id": quick["id"]}).status_code == 200
    assert client.get(f"{API}/vinted/unlinked-incomes").json() == []


def test_cancel_sale_withdraw_and_edit(client):
    item = make_item(client, purchase=bought())
    sold = sell(client, item["id"])
    assert client.patch(f"{API}/vinted/items/{item['id']}", json={"is_withdrawn": True}).status_code == 409

    assert client.delete(f"{API}/vinted/items/{item['id']}/sale").status_code == 204
    back = client.get(f"{API}/vinted/items/{item['id']}").json()
    assert back["status"] == "listed" and back["sale"] is None
    assert client.get(f"{API}/incomes/{sold['sale']['income_id']}").status_code == 404
    assert client.delete(f"{API}/vinted/items/{item['id']}/sale").status_code == 409

    withdrawn = client.patch(f"{API}/vinted/items/{item['id']}", json={"is_withdrawn": True}).json()
    assert withdrawn["status"] == "withdrawn"
    # Sold after all: back in the lists as sold.
    assert sell(client, item["id"])["status"] == "sold"
    client.delete(f"{API}/vinted/items/{item['id']}/sale")
    assert client.get(f"{API}/vinted/items/{item['id']}").json()["status"] == "listed"

    edited = client.patch(f"{API}/vinted/items/{item['id']}", json={"title": " Borsa marrone ", "note": "tracolla"})
    assert (edited.json()["title"], edited.json()["note"]) == ("Borsa marrone", "tracolla")
    cleared = client.patch(f"{API}/vinted/items/{item['id']}", json={"note": None}).json()
    assert cleared["note"] is None and cleared["title"] == "Borsa marrone"
    assert client.patch(f"{API}/vinted/items/{item['id']}", json={"title": "  "}).status_code == 422


def test_status_filter_and_order(client):
    a = make_item(client, title="A", purchase=bought(day="2026-10-01"))
    b = make_item(client, title="B", listed_on="2026-11-05")
    c = make_item(client, title="C", listed_on="2026-09-01")
    sell(client, c["id"], day="2026-11-20")
    d = make_item(client, title="D", listed_on="2026-11-06")
    client.patch(f"{API}/vinted/items/{d['id']}", json={"is_withdrawn": True})

    # Newest first; a sold item counts from its sale.
    assert [i["title"] for i in client.get(f"{API}/vinted/items").json()] == ["C", "D", "B", "A"]
    assert [i["id"] for i in client.get(f"{API}/vinted/items?status=listed").json()] == [b["id"], a["id"]]
    assert [i["id"] for i in client.get(f"{API}/vinted/items?status=sold").json()] == [c["id"]]
    assert [i["id"] for i in client.get(f"{API}/vinted/items?status=withdrawn").json()] == [d["id"]]
    assert client.get(f"{API}/vinted/items?status=other").status_code == 422


# --- the links from the household side ---------------------------------------------


def test_linked_expense_and_income_keep_the_vinted_category(client, categories):
    item = sell(client, make_item(client, purchase=bought())["id"])
    expense_id, income_id = item["purchase"]["expense_id"], item["sale"]["income_id"]

    moved = client.patch(f"{API}/expenses/{expense_id}", json={"category_id": categories["Abbigliamento"]})
    assert moved.status_code == 409
    assert "Borsa a tracolla" in moved.json()["detail"]
    assert client.patch(f"{API}/incomes/{income_id}", json={"category": "sale"}).status_code == 409

    # Amounts and dates are the item's own: changed in "Movimenti", changed here.
    assert client.patch(f"{API}/expenses/{expense_id}",
                        json={"amount": "11,50", "category_id": categories["Vinted"]}).status_code == 200
    assert client.patch(f"{API}/incomes/{income_id}", json={"amount": "26", "category": "vinted"}).status_code == 200
    updated = client.get(f"{API}/vinted/items/{item['id']}").json()
    assert (updated["purchase"]["amount_cents"], updated["sale"]["amount_cents"]) == (1150, 2600)
    assert updated["gain_cents"] == 1450


def test_deleting_the_expense_or_the_income_keeps_the_item(client):
    item = sell(client, make_item(client, purchase=bought())["id"])
    assert client.delete(f"{API}/expenses/{item['purchase']['expense_id']}").status_code == 204
    without_purchase = client.get(f"{API}/vinted/items/{item['id']}").json()
    assert without_purchase["purchase"] is None
    assert without_purchase["gain_cents"] == 2500

    assert client.delete(f"{API}/incomes/{item['sale']['income_id']}").status_code == 204
    assert client.get(f"{API}/vinted/items/{item['id']}").json()["status"] == "listed"


def test_deleting_the_item_deletes_its_money_and_photo(client, categories):
    item = sell(client, make_item(client, purchase=bought(merchant="Mercatino"))["id"])
    keep = make_expense(client, categories, category_id=categories["Vinted"], merchant="Vinted")
    client.put(f"{API}/vinted/items/{item['id']}/photo", json={"image": b64(JPEG), "thumb": b64(THUMB)})

    assert client.delete(f"{API}/vinted/items/{item['id']}").status_code == 204
    assert client.get(f"{API}/vinted/items/{item['id']}").status_code == 404
    assert [e["id"] for e in client.get(f"{API}/expenses").json()] == [keep["id"]]
    assert client.get(f"{API}/incomes").json() == []
    assert "Mercatino" not in [m["name"] for m in client.get(f"{API}/merchants").json()]
    assert client.get(f"{API}/vinted/items/{item['id']}/photo").status_code == 404
    assert client.delete(f"{API}/vinted/items/{item['id']}").status_code == 404


# --- photos ------------------------------------------------------------------------


def test_photo_upload_read_replace_delete(client):
    item = make_item(client)
    response = client.put(f"{API}/vinted/items/{item['id']}/photo", json={"image": b64(JPEG), "thumb": b64(THUMB)})
    assert response.status_code == 200
    token = response.json()["photo"]
    assert token and len(token) == 16
    assert client.get(f"{API}/vinted/items").json()[0]["photo"] == token

    photo = client.get(f"{API}/vinted/items/{item['id']}/photo?v={token}")
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/jpeg"
    assert photo.content == JPEG
    assert "immutable" in photo.headers["cache-control"]
    stale = client.get(f"{API}/vinted/items/{item['id']}/photo")
    assert "no-cache" in stale.headers["cache-control"]
    thumb = client.get(f"{API}/vinted/items/{item['id']}/photo/thumb?v={token}")
    assert thumb.content == THUMB

    other = JPEG + b"\x01"
    replaced = client.put(f"{API}/vinted/items/{item['id']}/photo", json={"image": b64(other), "thumb": b64(THUMB)})
    assert replaced.json()["photo"] != token
    assert client.get(f"{API}/vinted/items/{item['id']}/photo").content == other

    assert client.delete(f"{API}/vinted/items/{item['id']}/photo").status_code == 204
    assert client.get(f"{API}/vinted/items/{item['id']}").json()["photo"] is None
    assert client.get(f"{API}/vinted/items/{item['id']}/photo").status_code == 404


def test_photo_validation(client):
    item = make_item(client)

    def put(image, thumb=b64(THUMB)):
        return client.put(f"{API}/vinted/items/{item['id']}/photo", json={"image": image, "thumb": thumb})

    assert put(b64(b"\x89PNG\r\n\x1a\n" + bytes(100))).status_code == 422
    assert put("not base64!").status_code == 422
    assert put(b64(JPEG), b64(b"GIF89a")).status_code == 422
    assert put(b64(b"\xff\xd8\xff" + bytes(3 * 1024 * 1024))).status_code == 413
    assert client.put(f"{API}/vinted/items/999/photo",
                      json={"image": b64(JPEG), "thumb": b64(THUMB)}).status_code == 404
    assert client.get(f"{API}/vinted/items/{item['id']}").json()["photo"] is None


# --- summary, trend, household totals ----------------------------------------------


def _month_of_vinted(client, categories):
    """November 2026 as in the preview: 49 EUR of sales, 35 of expenses."""
    a = make_item(client, title="Borsa", purchase=bought("12", "2026-11-02"))
    sell(client, a["id"], "25", "2026-11-18")
    b = make_item(client, title="Giacca", listed_on="2026-11-01")
    sell(client, b["id"], "15", "2026-11-20")
    make_item(client, title="Tuta", purchase=bought("18,50", "2026-11-12"))
    d = make_item(client, title="Felpa", purchase=bought("4", "2026-10-25"))
    sell(client, d["id"], "9", "2026-11-08")
    make_expense(client, categories, category_id=categories["Vinted"], merchant="Vinted",
                 amount="4,50", expense_date="2026-11-10", note="Buste per spedizioni")
    e = make_item(client, title="Zaino", listed_on="2026-03-01")
    sell(client, e["id"], "30", "2026-03-05")
    f = make_item(client, title="Libri", listed_on="2025-12-01")
    sell(client, f["id"], "10", "2025-12-20")
    client.post(f"{API}/incomes", json={"amount": "1850", "category": "salary", "income_date": "2026-11-10"})


def test_summary_of_the_month(client, categories):
    _month_of_vinted(client, categories)
    summary = client.get(f"{API}/vinted/summary?month=2026-11").json()
    assert summary == {
        "month": "2026-11",
        "sales_cents": 4900, "sales_count": 3,
        "expense_cents": 3500, "expense_count": 3, "purchase_count": 2, "extra_count": 1,
        "balance_cents": 1400,
        "sold_count": 3, "sold_cents": 4900, "sold_cost_cents": 1600, "gain_cents": 3300,
        "year": 2026, "year_sales_count": 4, "year_sales_cents": 7900,
    }
    empty = client.get(f"{API}/vinted/summary?month=2026-07").json()
    assert (empty["sales_count"], empty["expense_count"], empty["balance_cents"]) == (0, 0, 0)
    assert empty["year_sales_count"] == 4
    assert client.get(f"{API}/vinted/summary?month=2026-13").status_code == 422

    # The household summary counts Vinted like any category.
    household = client.get(f"{API}/summary?month=2026-11").json()
    by_name = {c["category_name"]: c["total_cents"] for c in household["by_category"]}
    assert by_name["Vinted"] == 3500
    assert household["income_cents"] == 185000 + 4900


def test_trend_of_the_section(client, categories):
    _month_of_vinted(client, categories)
    trend = client.get(f"{API}/vinted/summary/trend?month=2026-11&months=3").json()
    assert [(m["month"], m["income_cents"], m["income_count"], m["expense_cents"], m["expense_count"],
             m["balance_cents"], m["voucher_cents"]) for m in trend] == [
        ("2026-09", 0, 0, 0, 0, 0, 0),
        ("2026-10", 0, 0, 400, 1, -400, 0),
        ("2026-11", 4900, 3, 3500, 3, 1400, 0),
    ]
    assert len(client.get(f"{API}/vinted/summary/trend?month=2026-11").json()) == 6
    assert client.get(f"{API}/vinted/summary/trend?month=2026-11&months=25").status_code == 422


# --- CSV, backup, access ---------------------------------------------------------------


def test_vinted_csv(client, categories):
    sold = sell(client, make_item(client, title="Borsa, marrone", purchase=bought("12", "2026-11-02"),
                                  note="tracolla")["id"], "25", "2026-11-18")
    own = sell(client, make_item(client, title="Giacca", listed_on="2026-11-01")["id"], "15", "2026-11-20")
    listed = make_item(client, title="Tuta", purchase=bought("18,50", "2026-11-12"))
    withdrawn = make_item(client, title="Stivali", listed_on="2026-10-08")
    client.patch(f"{API}/vinted/items/{withdrawn['id']}", json={"is_withdrawn": True})

    response = client.get(f"{API}/export/vinted.csv")
    assert response.status_code == 200
    assert 'filename="vinted_articoli.csv"' in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert rows[0] == VINTED_CSV_HEADER
    by_title = {row[0]: row for row in rows[1:]}
    assert [row[0] for row in rows[1:]] == ["Stivali", "Giacca", "Borsa, marrone", "Tuta"]  # oldest first
    assert by_title["Borsa, marrone"][1:10] == [
        "Venduto", "2026-11-02", "12.00", "2026-11-18", "25.00", "13.00", "16", "tracolla", "Fabio"]
    assert by_title["Giacca"][1:8] == ["Venduto", "", "", "2026-11-20", "15.00", "15.00", "19"]
    days = (PINNED_TODAY - date(2026, 11, 12)).days
    assert by_title["Tuta"][1:8] == ["In vendita", "2026-11-12", "18.50", "", "", "", str(days)]
    assert by_title["Stivali"][1:8] == ["Ritirato", "", "", "", "", "", ""]
    assert sold["id"] and own["id"] and listed["id"]

    excel = client.get(f"{API}/export/vinted.csv?format=excel_it")
    assert 'filename="vinted_articoli_excel.csv"' in excel.headers["content-disposition"]
    text = excel.content.decode("utf-8-sig")
    assert text.splitlines()[0] == ";".join(VINTED_CSV_HEADER)
    assert "Borsa, marrone;Venduto;2026-11-02;12,00;2026-11-18;25,00;13,00;16;tracolla;Fabio;" in text


def test_backup_and_restore_keep_items_and_photos(client):
    item = sell(client, make_item(client, purchase=bought())["id"])
    client.put(f"{API}/vinted/items/{item['id']}/photo", json={"image": b64(JPEG), "thumb": b64(THUMB)})
    backup = client.get(f"{API}/backup").content

    client.delete(f"{API}/vinted/items/{item['id']}")
    assert client.get(f"{API}/vinted/items").json() == []
    assert client.post(f"{API}/restore", content=backup).status_code == 200

    restored = client.get(f"{API}/vinted/items").json()
    assert [(i["id"], i["status"], i["gain_cents"]) for i in restored] == [(item["id"], "sold", 1300)]
    assert client.get(f"{API}/vinted/items/{item['id']}/photo").content == JPEG


def test_access_and_csrf(client, anon, app):
    assert anon.get(f"{API}/vinted/items").status_code == 401
    assert anon.get(f"{API}/vinted/summary?month=2026-11").status_code == 401
    assert anon.get(f"{API}/export/vinted.csv").status_code == 401
    item = make_item(client)
    assert anon.get(f"{API}/vinted/items/{item['id']}/photo").status_code == 401
    with TestClient(app) as bare:  # cookie but no X-Requested-With
        bare.cookies.set("spese_session", client.cookies["spese_session"])
        assert bare.get(f"{API}/vinted/items").status_code == 200
        assert bare.post(f"{API}/vinted/items", json={"title": "X"}).status_code == 403
        assert bare.post(f"{API}/vinted/items/{item['id']}/sale", json={"amount": "5"}).status_code == 403
        assert bare.put(f"{API}/vinted/items/{item['id']}/photo",
                        json={"image": b64(JPEG), "thumb": b64(THUMB)}).status_code == 403
        assert bare.delete(f"{API}/vinted/items/{item['id']}").status_code == 403
    assert len(client.get(f"{API}/vinted/items").json()) == 1
