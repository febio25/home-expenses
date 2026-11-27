"""0.9.0: search over expenses and incomes ("Movimenti"), and the totals of
any period ("Esplora"), for the household and for the Vinted section."""

from __future__ import annotations

from tests.conftest import make_expense
from tests.test_vinted import _month_of_vinted, bought, make_item, sell, users_of

API = "/api/v1"


def titles(rows, key="merchant_name"):
    return [(row["expense_date"] if "expense_date" in row else row["income_date"], row[key]) for row in rows]


def search(client, text, what="expenses", **params):
    response = client.get(f"{API}/{what}", params={"q": text, **params})
    assert response.status_code == 200, response.text
    return response.json()


# --- search: expenses ------------------------------------------------------------------


def _shops(client, categories):
    make_expense(client, categories, merchant="Esselunga", amount="78,50", expense_date="2026-11-10")
    make_expense(client, categories, merchant="ESSELUNGA", amount="12,50", expense_date="2026-09-16")
    make_expense(client, categories, merchant="Bar Centrale", amount="4,50", expense_date="2026-11-12",
                 category_id=categories["Ristoranti e bar"], note="Caffè con Luca")
    make_expense(client, categories, merchant="Q8", amount="60", expense_date="2026-10-03",
                 category_id=categories["Auto e trasporti"], note="carburante 50% sconto_x")
    make_expense(client, categories, merchant=None, amount="12,50", expense_date="2026-08-01",
                 category_id=categories["Salute"], note="Ticket visita")
    make_expense(client, categories, merchant="Lidl", amount="30", expense_date="2025-12-20")


def test_search_finds_merchants_in_every_month_newest_first(client, categories):
    _shops(client, categories)
    found = search(client, "esselunga")
    # "ESSELUNGA" is the same merchant, as first written.
    assert titles(found) == [("2026-11-10", "Esselunga"), ("2026-09-16", "Esselunga")]
    # Part of a name, any case, spaces tidied.
    assert len(search(client, "  SSELUN ")) == 2


def test_search_ignores_case_and_accents_in_notes_and_categories(client, categories):
    _shops(client, categories)
    assert titles(search(client, "caffe")) == [("2026-11-12", "Bar Centrale")]
    assert titles(search(client, "CAFFÈ")) == [("2026-11-12", "Bar Centrale")]
    # The category name: every expense of "Auto e trasporti".
    assert titles(search(client, "trasporti")) == [("2026-10-03", "Q8")]
    assert len(search(client, "spesa alimentare")) == 3  # Esselunga twice and Lidl
    # "%" and "_" are plain text, not wildcards.
    assert titles(search(client, "50%")) == [("2026-10-03", "Q8")]
    assert titles(search(client, "o_x")) == [("2026-10-03", "Q8")]
    assert search(client, "o%x") == []


def test_search_by_amount(client, categories):
    _shops(client, categories)
    found = search(client, "12,50")
    assert [(row["expense_date"], row["amount_cents"]) for row in found] == [
        ("2026-09-16", 1250), ("2026-08-01", 1250),
    ]
    assert len(search(client, "12.5")) == 2
    assert titles(search(client, "60")) == [("2026-10-03", "Q8")]
    assert titles(search(client, "60 €")) == [("2026-10-03", "Q8")]


def test_search_combines_with_range_and_category(client, categories):
    _shops(client, categories)
    assert titles(search(client, "esselunga", month="2026-11")) == [("2026-11-10", "Esselunga")]
    assert titles(search(client, "12,50", **{"from": "2026-09-01", "to": "2026-12-31"})) == [
        ("2026-09-16", "Esselunga")
    ]
    assert titles(search(client, "12,50", category_id=categories["Salute"])) == [("2026-08-01", None)]
    # Nothing found, an empty search, a search too long.
    assert search(client, "nessun negozio") == []
    assert len(search(client, "   ")) == 6  # no text: the plain list
    assert client.get(f"{API}/expenses", params={"q": "x" * 81}).status_code == 422


def test_search_finds_the_linked_vinted_item(client, categories):
    make_item(client, title="Giacca blazer Giesswein", purchase=bought("18,50", "2026-11-12"))
    make_expense(client, categories, merchant="Zara", expense_date="2026-11-13",
                 category_id=categories["Abbigliamento"], note="giacca per me")
    found = search(client, "giesswein")
    assert [(row["vinted_item_title"], row["amount_cents"]) for row in found] == [
        ("Giacca blazer Giesswein", 1850)
    ]
    assert len(search(client, "giacca")) == 2


# --- search: incomes ----------------------------------------------------------------------


def test_search_incomes(client):
    nastia = users_of(client)["Nastia"]
    for body in (
        {"amount": "1850", "category": "salary", "income_date": "2026-11-10"},
        {"amount": "1480", "category": "salary", "income_date": "2026-10-15", "received_by_user_id": nastia},
        {"amount": "126,50", "category": "refund", "income_date": "2026-09-20", "note": "730 rimborso Irpef"},
        {"amount": "160", "category": "meal_voucher", "income_date": "2026-11-01"},
        {"amount": "50", "category": "gift", "income_date": "2026-08-01", "note": "Compleanno, dalla nonna"},
    ):
        assert client.post(f"{API}/incomes", json=body).status_code == 201
    sold = sell(client, make_item(client, title="Zaino unicorno", listed_on="2026-06-01")["id"], "18", "2026-06-11")

    def dates(text, **params):
        return [row["income_date"] for row in search(client, text, "incomes", **params)]

    # Category names (the codes stay hidden), notes, amounts, Vinted titles.
    assert dates("stipendio") == ["2026-11-10", "2026-10-15"]
    assert dates("BUONI") == ["2026-11-01"]
    assert dates("irpef") == ["2026-09-20"]
    assert dates("126,50") == ["2026-09-20"]
    assert dates("nonna") == ["2026-08-01"]
    assert dates("unicorno") == [sold["sale"]["income_date"]]
    assert dates("vinted") == ["2026-06-11"]  # the category of the sale
    assert dates("salary") == []  # a code is not a name
    assert dates("stipendio", month="2026-10") == ["2026-10-15"]
    assert client.get(f"{API}/incomes", params={"q": "y" * 81}).status_code == 422


def test_search_needs_login(anon):
    assert anon.get(f"{API}/expenses?q=lidl").status_code == 401
    assert anon.get(f"{API}/incomes?q=lidl").status_code == 401


# --- period totals: household ----------------------------------------------------------------


def _year(client, categories):
    make_expense(client, categories, amount="100", expense_date="2026-01-01")
    make_expense(client, categories, amount="50,25", expense_date="2026-06-30")
    make_expense(client, categories, amount="20", expense_date="2026-07-01")
    make_expense(client, categories, amount="9,99", expense_date="2025-12-31")
    for body in (
        {"amount": "1850", "category": "salary", "income_date": "2026-06-10"},
        {"amount": "160", "category": "meal_voucher", "income_date": "2026-06-01"},
        {"amount": "1850", "category": "salary", "income_date": "2026-07-10"},
    ):
        assert client.post(f"{API}/incomes", json=body).status_code == 201


def period(client, start, end, section=""):
    response = client.get(f"{API}{section}/summary/period", params={"from": start, "to": end})
    assert response.status_code == 200, response.text
    return response.json()


def test_period_totals(client, categories):
    _year(client, categories)
    assert period(client, "2026-01-01", "2026-12-31") == {
        "start": "2026-01-01", "end": "2026-12-31",
        "income_cents": 386000, "income_count": 3, "voucher_cents": 16000,
        "expense_cents": 17025, "expense_count": 3, "planned_cents": 0, "planned_count": 0,
        "balance_cents": 386000 - 17025,
    }
    # Both ends included; a single day; a period with nothing.
    first_half = period(client, "2026-01-01", "2026-06-30")
    assert (first_half["expense_cents"], first_half["income_cents"]) == (15025, 201000)
    assert period(client, "2026-07-01", "2026-07-01")["expense_cents"] == 2000
    empty = period(client, "2024-01-01", "2024-12-31")
    assert (empty["income_count"], empty["expense_count"], empty["balance_cents"]) == (0, 0, 0)

    # The totals of a month match the monthly summary.
    june = period(client, "2026-06-01", "2026-06-30")
    summary = client.get(f"{API}/summary?month=2026-06").json()
    assert (june["expense_cents"], june["income_cents"], june["voucher_cents"]) == (
        summary["total_cents"], summary["income_cents"], summary["voucher_cents"])


def test_period_validation_and_access(client, anon):
    assert client.get(f"{API}/summary/period?from=2026-07-01&to=2026-06-30").status_code == 422
    assert client.get(f"{API}/summary/period?from=2026-07-01").status_code == 422
    assert client.get(f"{API}/summary/period?from=2026-13-01&to=2026-12-31").status_code == 422
    assert anon.get(f"{API}/summary/period?from=2026-01-01&to=2026-12-31").status_code == 401
    assert client.get(f"{API}/vinted/summary/period?from=2026-07-01&to=2026-06-30").status_code == 422
    assert anon.get(f"{API}/vinted/summary/period?from=2026-01-01&to=2026-12-31").status_code == 401


# --- period totals: Vinted ---------------------------------------------------------------------


def test_vinted_period_totals(client, categories):
    _month_of_vinted(client, categories)
    year = period(client, "2026-01-01", "2026-12-31", "/vinted")
    assert year == {
        "start": "2026-01-01", "end": "2026-12-31",
        "sales_cents": 7900, "sales_count": 4,
        "expense_cents": 3900, "expense_count": 4, "purchase_count": 3, "extra_count": 1,
        "balance_cents": 4000,
        "sold_count": 4, "sold_cents": 7900, "sold_cost_cents": 1600, "gain_cents": 6300,
    }
    # A month gives the figures of the month summary.
    november = period(client, "2026-11-01", "2026-11-30", "/vinted")
    summary = client.get(f"{API}/vinted/summary?month=2026-11").json()
    for key in ("sales_cents", "sales_count", "expense_cents", "expense_count", "purchase_count",
                "extra_count", "balance_cents", "sold_count", "sold_cents", "sold_cost_cents", "gain_cents"):
        assert november[key] == summary[key], key
    # Two dates of one's choice, across the year end.
    winter = period(client, "2025-12-15", "2026-03-31", "/vinted")
    assert (winter["sales_count"], winter["sales_cents"], winter["expense_count"]) == (2, 4000, 0)
