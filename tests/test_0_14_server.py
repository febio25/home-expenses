"""0.14.0, server side: search a page at a time with the totals of every
match, possible duplicates when saving an expense, merchants sorted by
recent use, categories reordered in one request, text cells of the Excel CSV
protected from formulas, incomes still expected in the month."""

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from tests.conftest import CSRF, NASTIA, make_expense
from tests.test_incomes import make_income

API = "/api/v1"


def login_nastia(app):
    client = TestClient(app, headers=CSRF)
    client.__enter__()
    response = client.post(f"{API}/auth/login", json={"username": "Nastia", "password": NASTIA["password"]})
    assert response.status_code == 200
    return client


# --- search a page at a time ---------------------------------------------------------


def _many_coffees(client, categories, count=7):
    """One coffee a day at the end of October and the start of November."""
    days = ["2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"]
    for index, day in enumerate(days[:count]):
        make_expense(client, categories, merchant="Bar Centrale", amount=f"{index + 1},00",
                     expense_date=day, category_id=categories["Ristoranti e bar"])
    make_expense(client, categories, merchant="Lidl", amount="30", expense_date="2026-11-02")


def test_expense_search_in_pages(client, categories):
    _many_coffees(client, categories)
    every = client.get(f"{API}/expenses", params={"q": "bar"}).json()
    assert len(every) == 7  # no limit: all of them, as before 0.14.0
    first = client.get(f"{API}/expenses", params={"q": "bar", "limit": 3}).json()
    second = client.get(f"{API}/expenses", params={"q": "bar", "limit": 3, "offset": 3}).json()
    last = client.get(f"{API}/expenses", params={"q": "bar", "limit": 3, "offset": 6}).json()
    assert [row["id"] for row in first + second + last] == [row["id"] for row in every]
    assert len(last) == 1
    # Newest first, as the list of a month.
    assert first[0]["expense_date"] == "2026-11-04"


def test_paging_also_works_on_a_month_and_on_incomes(client, categories):
    _many_coffees(client, categories)
    page = client.get(f"{API}/expenses", params={"month": "2026-11", "limit": 2}).json()
    assert [row["expense_date"] for row in page] == ["2026-11-04", "2026-11-03"]
    for day in ("2026-11-01", "2026-11-05", "2026-11-09"):
        make_income(client, income_date=day, note="stipendio")
    page = client.get(f"{API}/incomes", params={"q": "stipendio", "limit": 2, "offset": 1}).json()
    assert [row["income_date"] for row in page] == ["2026-11-05", "2026-11-01"]


def test_paging_limits_are_checked(client, categories):
    assert client.get(f"{API}/expenses", params={"limit": 0}).status_code == 422
    assert client.get(f"{API}/expenses", params={"limit": 501}).status_code == 422
    assert client.get(f"{API}/expenses", params={"limit": 5, "offset": -1}).status_code == 422


def test_search_totals_count_every_match_by_month(client, categories):
    _many_coffees(client, categories)
    totals = client.get(f"{API}/summary/search/expenses", params={"q": "bar"}).json()
    assert totals["count"] == 7
    assert totals["total_cents"] == sum(range(1, 8)) * 100
    assert totals["months"] == [
        {"month": "2026-11", "count": 4, "total_cents": (4 + 5 + 6 + 7) * 100},
        {"month": "2026-10", "count": 3, "total_cents": (1 + 2 + 3) * 100},
    ]
    # Same rows as the list: the category name is searched too.
    by_category = client.get(f"{API}/summary/search/expenses", params={"q": "ristoranti"}).json()
    assert by_category["count"] == 7
    empty = client.get(f"{API}/summary/search/expenses", params={"q": "nulla"}).json()
    assert empty == {"count": 0, "total_cents": 0, "months": []}
    # 0.18.0: the text is optional (the filters search without it): every expense counts.
    assert client.get(f"{API}/summary/search/expenses").json()["count"] >= 7


def test_income_search_totals(client):
    make_income(client, income_date="2026-10-27", amount="1800")
    make_income(client, income_date="2026-11-27", amount="1850")
    make_income(client, income_date="2026-11-10", amount="20", category="gift", note="compleanno")
    totals = client.get(f"{API}/summary/search/incomes", params={"q": "stipendio"}).json()
    assert totals["count"] == 2
    assert totals["total_cents"] == 365000
    assert [month["month"] for month in totals["months"]] == ["2026-11", "2026-10"]
    assert client.get(f"{API}/summary/search/incomes", params={"q": "compleanno"}).json()["count"] == 1


# --- possible duplicates --------------------------------------------------------------


def test_a_new_expense_lists_the_ones_that_look_alike(client, categories, app):
    first = make_expense(client, categories, merchant="Esselunga", amount="45,20")
    assert first["possible_duplicates"] == []

    nastia = login_nastia(app)
    try:
        hers = make_expense(nastia, categories, merchant="esselunga ", amount="45.2")
    finally:
        nastia.__exit__(None, None, None)
    duplicates = hers["possible_duplicates"]
    assert [d["id"] for d in duplicates] == [first["id"]]
    assert duplicates[0]["created_by_name"] == "Fabio"
    assert duplicates[0]["merchant_name"] == "Esselunga"
    # It is saved anyway: the list only informs.
    assert len(client.get(f"{API}/expenses").json()) == 2

    # The same person entering it again is reported too.
    again = make_expense(client, categories, merchant="Esselunga", amount="45,20")
    assert [d["id"] for d in again["possible_duplicates"]] == [first["id"], hers["id"]]


def test_what_is_not_a_duplicate(client, categories):
    make_expense(client, categories, merchant="Esselunga", amount="45,20")
    assert make_expense(client, categories, merchant="Esselunga", amount="45,21")["possible_duplicates"] == []
    assert make_expense(client, categories, merchant="Coop", amount="45,20")["possible_duplicates"] == []
    assert make_expense(
        client, categories, merchant="Esselunga", amount="45,20", expense_date="2026-11-14"
    )["possible_duplicates"] == []
    # Without a merchant: the same category and no merchant on the other one.
    make_expense(client, categories, merchant=None, amount="3", category_id=categories["Varie"])
    assert make_expense(
        client, categories, merchant=None, amount="3", category_id=categories["Salute"]
    )["possible_duplicates"] == []
    assert len(make_expense(
        client, categories, merchant=None, amount="3", category_id=categories["Varie"]
    )["possible_duplicates"]) == 1


def test_a_retry_with_the_same_uuid_is_not_its_own_duplicate(client, categories):
    body = {"amount": "9", "category_id": categories["Varie"], "merchant": "Bar",
            "expense_date": "2026-11-13", "client_uuid": "retry-0001"}
    created = client.post(f"{API}/expenses", json=body)
    retried = client.post(f"{API}/expenses", json=body)
    assert (created.status_code, retried.status_code) == (201, 200)
    assert retried.json()["possible_duplicates"] == []


# --- merchants by recent use ------------------------------------------------------------


def test_merchants_used_recently_come_first(client, categories, pinned_today):
    # Pinned "today" is 30 June 2027: the last 90 days start on 1 April.
    for day in ("2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04"):
        make_expense(client, categories, merchant="Vecchio Bar", expense_date=day)
    make_expense(client, categories, merchant="Nuovo Bar", expense_date="2027-06-01")
    make_expense(client, categories, merchant="Nuovo Bar", expense_date="2027-06-02")
    make_expense(client, categories, merchant="Mai più", expense_date="2026-01-02")
    merchants = client.get(f"{API}/merchants").json()
    assert [m["name"] for m in merchants] == ["Nuovo Bar", "Vecchio Bar", "Mai più"]
    assert [(m["recent_count"], m["expense_count"]) for m in merchants] == [(2, 2), (0, 4), (0, 1)]


# --- categories in one request -----------------------------------------------------------------


def test_reorder_categories(client):
    every = client.get(f"{API}/categories", params={"include_inactive": True}).json()
    ids = [c["id"] for c in every]
    reordered = [ids[1], ids[0], *ids[2:]]
    response = client.put(f"{API}/categories/order", json={"ids": reordered})
    assert response.status_code == 200, response.text
    assert [c["id"] for c in response.json()] == reordered
    assert [c["id"] for c in client.get(f"{API}/categories").json()] == reordered
    assert [c["sort_order"] for c in response.json()][:3] == [10, 20, 30]


def test_reorder_needs_every_category_once(client):
    ids = [c["id"] for c in client.get(f"{API}/categories", params={"include_inactive": True}).json()]
    for wrong in (ids[:-1], [*ids, ids[0]], [*ids[:-1], 9999]):
        response = client.put(f"{API}/categories/order", json={"ids": wrong})
        assert response.status_code == 409
        assert "ricarica" in response.json()["detail"]
    assert client.put(f"{API}/categories/order", json={"ids": []}).status_code == 422


# --- Excel: text that looks like a formula ----------------------------------------------------


def _rows(text, delimiter):
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def test_excel_flavour_protects_text_that_looks_like_a_formula(client, categories):
    make_expense(client, categories, merchant="+Bar", note="-10% saldi")
    make_expense(client, categories, merchant="@casa", note="=SOMMA(1;2)", amount="3")
    make_expense(client, categories, merchant="Lidl", note="normale - con trattino", amount="4")
    excel = _rows(client.get(f"{API}/export.csv", params={"format": "excel_it"}).content.decode("utf-8-sig"), ";")
    assert [row[3:5] for row in excel[1:]] == [
        ["'+Bar", "'-10% saldi"],
        ["'@casa", "'=SOMMA(1;2)"],
        ["Lidl", "normale - con trattino"],
    ]
    assert [row[1] for row in excel[1:]] == ["12,50", "3,00", "4,00"]  # amounts stay numbers
    # The standard flavour, the one for the AI, is untouched.
    standard = _rows(client.get(f"{API}/export.csv").text, ",")
    assert [row[3:5] for row in standard[1:3]] == [["+Bar", "-10% saldi"], ["@casa", "=SOMMA(1;2)"]]


def test_excel_flavour_keeps_negative_amounts_as_numbers():
    from app.routers.export import excel_text

    assert excel_text("-5,00") == "-5,00"
    assert excel_text("-5") == "-5"
    assert excel_text("-cinque") == "'-cinque"
    assert excel_text("\tnota") == "'\tnota"
    assert excel_text("2026-11-13") == "2026-11-13"


# --- incomes still expected in the month ----------------------------------------------------------


def _template(client, **overrides):
    body = {"amount": "2100", "category": "salary", "interval_months": 1, "next_due": "2026-11-27"}
    body.update(overrides)
    response = client.post(f"{API}/recurring-incomes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_summary_lists_the_recurring_incomes_due_in_the_month(client, categories):
    users = {u["display_name"]: u["id"] for u in client.get(f"{API}/users").json()}
    salary = _template(client)
    _template(client, amount="1750", next_due="2026-11-30", received_by_user_id=users["Nastia"])
    _template(client, amount="160", category="meal_voucher", next_due="2026-12-01")  # next month
    paused = _template(client, amount="99", next_due="2026-11-15")
    client.patch(f"{API}/recurring-incomes/{paused['id']}", json={"is_active": False})
    make_expense(client, categories, amount="2400")
    make_income(client, amount="63,33", category="vinted", income_date="2026-11-05")

    summary = client.get(f"{API}/summary", params={"month": "2026-11"}).json()
    assert summary["expected_income_cents"] == 385000
    assert [(e["category_name"], e["received_by_name"], e["due_date"], e["amount_cents"])
            for e in summary["expected_incomes"]] == [
        ("Stipendio", "Fabio", "2026-11-27", 210000),
        ("Stipendio", "Nastia", "2026-11-30", 175000),
    ]
    assert summary["balance_cents"] == 6333 - 240000  # unchanged: only what happened

    # Registered: no longer expected.
    registered = client.post(
        f"{API}/recurring-incomes/{salary['id']}/register", json={"due_date": "2026-11-27"}
    )
    assert registered.status_code == 201, registered.text
    summary = client.get(f"{API}/summary", params={"month": "2026-11"}).json()
    assert summary["expected_income_cents"] == 175000
    december = client.get(f"{API}/summary", params={"month": "2026-12"}).json()
    # The salary's next due date moved to December, with the vouchers.
    assert december["expected_income_cents"] == 210000 + 16000
