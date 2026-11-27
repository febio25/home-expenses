"""0.18.0: tags in the notes (F2), the filters of the search (F6), the
planned expenses in "Esplora" (F10)."""

from __future__ import annotations

from app.tags import clean_tag, has_tag, tags_in
from tests.conftest import make_expense

API = "/api/v1"


# --- tags -------------------------------------------------------------------------------


def test_tags_in_a_note():
    assert tags_in("Cena #Vacanze-2026 con #amici, #vacanze-2026 di nuovo") == ["Vacanze-2026", "amici"]
    assert tags_in("AT&T#1, a#b, # solo, #-, ##doppio") == ["doppio"]
    assert tags_in("#casa- e #caffè_bar") == ["casa", "caffè_bar"]
    assert tags_in(None) == [] and tags_in("niente") == []
    assert clean_tag("#Caffè_Bar") == "caffe_bar" and clean_tag("vacanze") == "vacanze"
    assert clean_tag("#") is None and clean_tag("-x") is None
    assert has_tag("pranzo #Caffè_bar", "caffe_bar") == 1
    assert has_tag("pranzo #caffe_barista", "caffe_bar") == 0


def test_list_of_tags(client, categories):
    make_expense(client, categories, amount="10", note="Treno #vacanze", expense_date="2026-08-01")
    make_expense(client, categories, amount="20", note="Hotel #Vacanze #mare", expense_date="2026-08-03")
    make_expense(client, categories, amount="5", note="Vernice #casa", expense_date="2026-09-01")
    make_expense(client, categories, amount="7", note="senza etichette", expense_date="2026-09-02")
    tags = client.get(f"{API}/tags").json()
    assert tags == [
        {"tag": "casa", "count": 1, "total_cents": 500, "last_date": "2026-09-01"},
        {"tag": "Vacanze", "count": 2, "total_cents": 3000, "last_date": "2026-08-03"},
        {"tag": "mare", "count": 1, "total_cents": 2000, "last_date": "2026-08-03"},
    ]


def test_tags_need_a_session(anon):
    assert anon.get(f"{API}/tags").status_code == 401


# --- filters of the search ------------------------------------------------------------------


def test_filters_of_the_list_and_of_the_totals(client, categories):
    users = {u["display_name"]: u["id"] for u in client.get(f"{API}/users").json()}
    food, home = categories["Spesa alimentare"], categories["Casa e utenze"]
    make_expense(client, categories, amount="10", category_id=food, expense_date="2026-10-01",
                 note="#vacanze")
    make_expense(client, categories, amount="20", category_id=food, expense_date="2026-11-02",
                 paid_by_user_id=users["Nastia"], payment_method="cash")
    make_expense(client, categories, amount="30", category_id=home, expense_date="2026-11-03",
                 paid_by_user_id=users["Nastia"], note="Lampada #Vacanze")
    make_expense(client, categories, amount="40", category_id=home, expense_date="2026-11-04")

    def both(**params):
        rows = client.get(f"{API}/expenses", params=params).json()
        totals = client.get(f"{API}/summary/search/expenses", params=params).json()
        assert totals["count"] == len(rows)
        assert totals["total_cents"] == sum(row["amount_cents"] for row in rows)
        return sorted(row["amount_cents"] for row in rows), totals

    assert both(paid_by_user_id=users["Nastia"])[0] == [2000, 3000]
    assert both(payment_method="cash")[0] == [2000]
    assert both(tag="vacanze")[0] == [1000, 3000]
    assert both(tag="#VACANZE", category_id=home)[0] == [3000]
    assert both(tag="#")[0] == []
    assert both(category_id=food, **{"from": "2026-11-01", "to": "2026-11-30"})[0] == [2000]
    assert both(q="lampada", paid_by_user_id=users["Nastia"])[0] == [3000]
    _, totals = both()  # no filter at all: every expense, month by month
    assert totals["count"] == 4
    assert [m["month"] for m in totals["months"]] == ["2026-11", "2026-10"]
    assert client.get(f"{API}/expenses", params={"payment_method": "bitcoin"}).status_code == 422


# --- «Esplora» with the planned expenses -------------------------------------------------------


def test_period_names_the_planned_expenses(client, categories, pinned_today):
    make_expense(client, categories, amount="10", expense_date="2027-06-30")
    make_expense(client, categories, amount="25", expense_date="2027-07-05")
    make_expense(client, categories, amount="5", expense_date="2027-07-31")
    body = client.get(f"{API}/summary/period", params={"from": "2027-06-01", "to": "2027-07-31"}).json()
    assert body["expense_cents"] == 4000 and body["expense_count"] == 3
    assert body["planned_cents"] == 3000 and body["planned_count"] == 2
    past = client.get(f"{API}/summary/period", params={"from": "2027-06-01", "to": "2027-06-30"}).json()
    assert past["planned_cents"] == 0 and past["planned_count"] == 0


# --- the text of the export ---------------------------------------------------------------------


def test_brief_explains_the_tags(client, categories):
    make_expense(client, categories, amount="10", note="#vacanze treno", expense_date="2026-11-01")
    make_expense(client, categories, amount="10", note="#Vacanze #mare", expense_date="2026-11-02")
    make_expense(client, categories, amount="10", note="#altro-mese", expense_date="2026-10-02")
    text = client.get(f"{API}/export/brief", params={"month": "2026-11"}).json()["text"]
    assert "Etichette nella nota: le parole che iniziano con # (qui #Vacanze, #mare)" in text
    assert "#altro-mese" not in text
    plain = client.get(f"{API}/export/brief", params={"month": "2026-10", "what": "incomes"}).json()["text"]
    assert "Etichette" not in plain
