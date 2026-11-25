import csv
import io
import sqlite3

from fastapi.testclient import TestClient

from tests.conftest import CSRF, NASTIA, make_expense, strip_vinted_schema

API = "/api/v1"
INCOME_HEADER = ["data", "importo", "categoria", "nota", "ricevuto_da", "inserito_da", "creato_il"]


def make_income(client, **overrides):
    body = {"amount": "1850,00", "category": "salary", "income_date": "2026-11-10"}
    body.update(overrides)
    response = client.post(f"{API}/incomes", json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


def users_of(client):
    return {u["display_name"]: u["id"] for u in client.get(f"{API}/users").json()}


# --- entries ------------------------------------------------------------------


def test_categories_are_a_fixed_list(client, anon):
    assert client.get(f"{API}/incomes/categories").json() == [
        {"code": "salary", "name": "Stipendio", "icon": "briefcase"},
        {"code": "refund", "name": "Rimborsi", "icon": "receipt-refund"},
        {"code": "gift", "name": "Regali", "icon": "gift"},
        {"code": "sale", "name": "Vendite", "icon": "tag"},
        {"code": "vinted", "name": "Vinted", "icon": "hanger"},  # 0.8.0, next to the other sales
        {"code": "other", "name": "Altro", "icon": "dots"},
        {"code": "meal_voucher", "name": "Buoni pasto", "icon": "tools-kitchen-2"},  # 0.7.0, last as asked
    ]
    assert anon.get(f"{API}/incomes/categories").status_code == 401


def test_create_and_read(client):
    income = make_income(client, note="  ottobre ")
    assert income["amount_cents"] == 185000
    assert income["category"] == "salary"
    assert income["category_name"] == "Stipendio"
    assert income["income_date"] == "2026-11-10"
    assert income["note"] == "ottobre"
    assert income["received_by_name"] == "Fabio"   # defaults to the logged-in user
    assert income["created_by_name"] == "Fabio"
    assert client.get(f"{API}/incomes/{income['id']}").json() == income

    blank = make_income(client, note="   ", category="gift", amount="50")
    assert blank["note"] is None
    assert blank["category_name"] == "Regali"


def test_validation(client):
    def post(**overrides):
        body = {"amount": "10", "category": "other", "income_date": "2026-11-10"}
        body.update(overrides)
        return client.post(f"{API}/incomes", json=body)

    for bad in ("", "abc", "0", "-3", "12,345", "1.234"):
        response = post(amount=bad)
        assert response.status_code == 422, bad
        assert isinstance(response.json()["detail"], str)

    assert post(category="bonus").status_code == 422      # not in the fixed list
    assert post(category=None).status_code == 422
    future = post(income_date="2027-07-02")                # pinned today + 2 days
    assert future.status_code == 422
    assert future.json()["detail"] == "La data non può essere nel futuro."
    assert post(income_date="2027-07-01").status_code == 201  # one day of tolerance (time zone)
    assert post(income_date="1999-12-31").status_code == 422
    unknown = post(received_by_user_id=9999)
    assert unknown.status_code == 422
    assert unknown.json()["detail"] == "Utente non valido."


def test_retry_with_same_client_uuid_does_not_duplicate(client):
    body = {
        "amount": "120,50",
        "category": "refund",
        "income_date": "2026-11-12",
        "client_uuid": "6f1c2b9e-0d7a-4c55-9e1b-2a3c4d5e6f70",
    }
    first = client.post(f"{API}/incomes", json=body)
    retry = client.post(f"{API}/incomes", json=body)
    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    assert len(client.get(f"{API}/incomes").json()) == 1


def test_list_by_month_and_range(client):
    make_income(client, income_date="2026-10-31", amount="1")
    make_income(client, income_date="2026-11-01", amount="2")
    make_income(client, income_date="2026-11-30", amount="3")
    make_income(client, income_date="2026-12-01", amount="4")

    november = client.get(f"{API}/incomes?month=2026-11").json()
    assert [i["amount_cents"] for i in november] == [300, 200]  # newest first

    ranged = client.get(f"{API}/incomes?from=2026-10-31&to=2026-11-01").json()
    assert sorted(i["amount_cents"] for i in ranged) == [100, 200]

    assert len(client.get(f"{API}/incomes").json()) == 4
    assert client.get(f"{API}/incomes?month=2026-13").status_code == 422
    assert client.get(f"{API}/incomes?month=0000-01").status_code == 422
    assert client.get(f"{API}/incomes?from=2026-12-01&to=2026-11-01").status_code == 422


def test_update(client):
    income = make_income(client, note="nota")
    users = users_of(client)
    updated = client.patch(
        f"{API}/incomes/{income['id']}",
        json={
            "amount": "1.900,00",
            "category": "other",
            "income_date": "2026-11-05",
            "received_by_user_id": users["Nastia"],
            "note": "premio",
        },
    ).json()
    assert updated["amount_cents"] == 190000
    assert updated["category_name"] == "Altro"
    assert updated["income_date"] == "2026-11-05"
    assert updated["received_by_name"] == "Nastia"
    assert updated["created_by_name"] == "Fabio"
    assert updated["note"] == "premio"
    assert updated["updated_at"] >= income["updated_at"]


def test_partial_update_and_required_fields(client):
    income = make_income(client, note="nota")
    path = f"{API}/incomes/{income['id']}"
    updated = client.patch(path, json={"amount": "10"}).json()
    assert updated["amount_cents"] == 1000
    assert updated["category"] == "salary"
    assert updated["note"] == "nota"

    assert client.patch(path, json={"note": None}).json()["note"] is None
    for field in ("amount", "category", "income_date", "received_by_user_id"):
        assert client.patch(path, json={field: None}).status_code == 422, field
    assert client.patch(path, json={"category": "bonus"}).status_code == 422
    assert client.patch(path, json={"income_date": "2030-01-01"}).status_code == 422
    assert client.patch(path, json={"received_by_user_id": 9999}).status_code == 422
    assert client.patch(f"{API}/incomes/9999", json={"amount": "1"}).status_code == 404
    assert client.get(path).json()["amount_cents"] == 1000  # failed patches changed nothing


def test_delete(client):
    income = make_income(client)
    assert client.delete(f"{API}/incomes/{income['id']}").status_code == 204
    assert client.get(f"{API}/incomes/{income['id']}").status_code == 404
    assert client.delete(f"{API}/incomes/{income['id']}").status_code == 404


def test_both_users_see_and_edit_the_same_incomes(client, app):
    mine = make_income(client)
    with TestClient(app, headers=CSRF) as nastia:
        login = nastia.post(
            f"{API}/auth/login", json={"username": "Nastia", "password": NASTIA["password"]}
        )
        assert login.status_code == 200
        assert [i["id"] for i in nastia.get(f"{API}/incomes").json()] == [mine["id"]]
        hers = make_income(nastia, amount="1600")
        assert hers["received_by_name"] == "Nastia"
        assert hers["created_by_name"] == "Nastia"
        assert nastia.patch(f"{API}/incomes/{mine['id']}", json={"amount": "1860"}).status_code == 200
    assert len(client.get(f"{API}/incomes").json()) == 2
    assert client.get(f"{API}/incomes/{mine['id']}").json()["amount_cents"] == 186000


def test_access_rules(client, anon, app):
    assert anon.get(f"{API}/incomes").status_code == 401
    assert anon.get(f"{API}/summary/trend?month=2026-11").status_code == 401
    assert anon.get(f"{API}/export/incomes.csv").status_code == 401
    income = make_income(client)
    # Cookie-authenticated writes need the CSRF header; reads do not.
    with TestClient(app) as bare:
        bare.cookies.set("spese_session", client.cookies["spese_session"])
        assert bare.get(f"{API}/incomes").status_code == 200
        assert bare.delete(f"{API}/incomes/{income['id']}").status_code == 403
        created = bare.post(
            f"{API}/incomes", json={"amount": "5", "category": "gift", "income_date": "2026-11-10"}
        )
        assert created.status_code == 403
    assert len(client.get(f"{API}/incomes").json()) == 1


def test_incomes_leave_expenses_alone(client, categories):
    expense = make_expense(client, categories, amount="40", expense_date="2026-11-10")
    before_csv = client.get(f"{API}/export.csv?month=2026-11").content
    make_income(client, income_date="2026-11-10")
    assert [e["id"] for e in client.get(f"{API}/expenses").json()] == [expense["id"]]
    assert client.get(f"{API}/export.csv?month=2026-11").content == before_csv
    summary = client.get(f"{API}/summary?month=2026-11").json()
    assert summary["total_cents"] == 4000 and summary["expense_count"] == 1


# --- summary and trend ----------------------------------------------------------


def test_summary_includes_incomes_and_the_difference(client, categories):
    make_expense(client, categories, amount="10", expense_date="2026-11-03")
    make_expense(client, categories, amount="40", expense_date="2026-11-20")
    make_income(client, amount="1850", income_date="2026-11-10")
    make_income(client, amount="120,50", category="refund", income_date="2026-11-25")
    make_income(client, amount="999", income_date="2026-10-10")

    november = client.get(f"{API}/summary?month=2026-11").json()
    assert november["total_cents"] == 5000
    assert november["income_cents"] == 197050
    assert november["income_count"] == 2
    assert november["balance_cents"] == 192050

    # Incomes only: no expense categories, positive difference.
    october = client.get(f"{API}/summary?month=2026-10").json()
    assert october["total_cents"] == 0 and october["by_category"] == []
    assert october["income_cents"] == 99900 and october["balance_cents"] == 99900

    # Expenses only: no income recorded, the difference is minus the expenses.
    make_expense(client, categories, amount="7", expense_date="2026-09-01")
    september = client.get(f"{API}/summary?month=2026-09").json()
    assert september["income_count"] == 0
    assert september["balance_cents"] == -700


def test_trend_lists_every_month_of_the_window(client, categories):
    make_expense(client, categories, amount="10", expense_date="2026-06-01")
    make_expense(client, categories, amount="20", expense_date="2026-11-30")
    make_expense(client, categories, amount="5", expense_date="2026-11-01")
    make_expense(client, categories, amount="99", expense_date="2026-05-31")  # outside
    make_income(client, amount="100", income_date="2026-06-15")
    make_income(client, amount="300", income_date="2026-11-10")
    make_income(client, amount="50", income_date="2026-12-01")              # outside

    trend = client.get(f"{API}/summary/trend?month=2026-11").json()  # 6 months by default
    assert [m["month"] for m in trend] == [
        "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11",
    ]
    june, november = trend[0], trend[-1]
    assert (june["expense_cents"], june["expense_count"]) == (1000, 1)
    assert (june["income_cents"], june["income_count"]) == (10000, 1)
    assert june["balance_cents"] == 9000
    assert (november["expense_cents"], november["expense_count"]) == (2500, 2)
    assert november["balance_cents"] == 30000 - 2500
    for empty in trend[1:5]:
        assert empty["income_cents"] == empty["expense_cents"] == empty["balance_cents"] == 0
        assert empty["income_count"] == empty["expense_count"] == 0

    # The same figures as the monthly summary.
    summary = client.get(f"{API}/summary?month=2026-11").json()
    assert summary["total_cents"] == november["expense_cents"]
    assert summary["income_cents"] == november["income_cents"]


def test_trend_window(client):
    across = client.get(f"{API}/summary/trend?month=2027-02&months=6").json()
    assert [m["month"] for m in across] == [
        "2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02",
    ]
    assert [m["month"] for m in client.get(f"{API}/summary/trend?month=2026-11&months=1").json()] == [
        "2026-11"
    ]
    assert len(client.get(f"{API}/summary/trend?month=2026-11&months=24").json()) == 24
    for bad in ("months=0", "months=25", "months=x"):
        assert client.get(f"{API}/summary/trend?month=2026-11&{bad}").status_code == 422, bad
    assert client.get(f"{API}/summary/trend").status_code == 422
    assert client.get(f"{API}/summary/trend?month=2026-13").status_code == 422
    assert client.get(f"{API}/summary/trend?month=0001-03&months=6").status_code == 422


# --- CSV --------------------------------------------------------------------------


def _seed(client):
    users = users_of(client)
    make_income(
        client, amount="1234,56", income_date="2026-11-27", note='tredicesima, "anticipo"; parte',
    )
    make_income(
        client, amount="0,05", category="refund", income_date="2026-11-02",
        received_by_user_id=users["Nastia"], note="Caffè rimborsato",
    )
    make_income(client, amount="7", category="sale", income_date="2026-12-05")


def test_incomes_csv_standard(client):
    _seed(client)
    response = client.get(f"{API}/export/incomes.csv?month=2026-11")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="entrate_2026-11.csv"' in response.headers["content-disposition"]
    assert not response.content.startswith(b"\xef\xbb\xbf")  # no BOM for parsers

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert rows[0] == INCOME_HEADER
    assert len(rows) == 3  # header + the two November incomes, oldest first
    first, second = rows[1], rows[2]
    assert first[:6] == ["2026-11-02", "0.05", "Rimborsi", "Caffè rimborsato", "Nastia", "Fabio"]
    assert second[:6] == [
        "2026-11-27",
        "1234.56",
        "Stipendio",
        'tredicesima, "anticipo"; parte',   # comma and quotes survive quoting
        "Fabio",
        "Fabio",
    ]
    assert len(first[6]) == 20 and first[6].endswith("Z") and first[6][10] == "T"


def test_incomes_csv_excel_italian(client):
    _seed(client)
    response = client.get(f"{API}/export/incomes.csv?month=2026-11&format=excel_it")
    assert response.content.startswith(b"\xef\xbb\xbf")  # BOM so Excel reads accents
    assert 'filename="entrate_2026-11_excel.csv"' in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0] == INCOME_HEADER
    assert rows[1][1] == "0,05"
    assert rows[2][1] == "1234,56"                      # decimal comma, no thousands separator
    assert rows[2][3] == 'tredicesima, "anticipo"; parte'
    assert rows[1][3] == "Caffè rimborsato"


def test_incomes_csv_by_range_and_all(client):
    _seed(client)
    ranged = client.get(f"{API}/export/incomes.csv?from=2026-11-03&to=2026-12-31")
    rows = list(csv.reader(io.StringIO(ranged.text)))
    assert [r[0] for r in rows[1:]] == ["2026-11-27", "2026-12-05"]
    assert rows[2][3] == ""  # no note -> empty field
    assert "entrate_2026-11-03_2026-12-31.csv" in ranged.headers["content-disposition"]

    everything = client.get(f"{API}/export/incomes.csv")
    assert len(everything.text.strip().splitlines()) == 4
    assert "entrate_tutte.csv" in everything.headers["content-disposition"]

    empty = client.get(f"{API}/export/incomes.csv?month=2020-01")
    assert empty.text.strip() == ",".join(INCOME_HEADER)
    assert client.get(f"{API}/export/incomes.csv?format=nope").status_code == 422


# --- backup and restore -------------------------------------------------------------


def test_backup_and_restore_keep_incomes(client):
    _seed(client)
    backup = client.get(f"{API}/backup").content
    before = client.get(f"{API}/incomes").json()
    for income in before:
        client.delete(f"{API}/incomes/{income['id']}")
    assert client.get(f"{API}/incomes").json() == []

    restored = client.post(
        f"{API}/restore", content=backup, headers={"Content-Type": "application/octet-stream"}
    )
    assert restored.status_code == 200, restored.text
    assert client.get(f"{API}/incomes").json() == before


def test_restore_of_a_backup_without_incomes(client, categories, tmp_path):
    """A backup made by 0.2.x-0.4.x (schema 2) restores and gets the incomes table."""
    from app.config import get_settings
    from app.db import latest_schema_version

    make_expense(client, categories)
    old = tmp_path / "schema2.db"
    old.write_bytes(client.get(f"{API}/backup").content)
    conn = sqlite3.connect(old)
    conn.execute("DROP TABLE incomes")
    conn.execute("DROP TABLE recurring_incomes")  # schema 4, newer still
    strip_vinted_schema(conn)  # schema 5
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()

    make_income(client)  # gone after the restore: the backup has no incomes
    response = client.post(
        f"{API}/restore", content=old.read_bytes(), headers={"Content-Type": "application/octet-stream"}
    )
    assert response.status_code == 200, response.text
    assert client.get(f"{API}/incomes").json() == []
    assert len(client.get(f"{API}/expenses").json()) == 1
    live = sqlite3.connect(get_settings().db_path)
    try:
        assert live.execute("PRAGMA user_version").fetchone()[0] == latest_schema_version()
    finally:
        live.close()
    assert make_income(client)["amount_cents"] == 185000


# --- meal vouchers and the income summary (0.7.0) ------------------------------


def test_meal_vouchers_are_an_income_shown_on_their_own(client, categories):
    make_expense(client, categories, amount="64", expense_date="2026-11-07")   # paid with vouchers, in full
    make_income(client, amount="1850", income_date="2026-11-03")
    vouchers = make_income(client, amount="160", category="meal_voucher", income_date="2026-11-30")
    assert vouchers["category_name"] == "Buoni pasto"
    make_income(client, amount="152", category="meal_voucher", income_date="2026-10-31")

    november = client.get(f"{API}/summary?month=2026-11").json()
    assert november["income_cents"] == 201000            # vouchers are part of the incomes
    assert november["voucher_cents"] == 16000
    assert november["balance_cents"] == 201000 - 6400
    october = client.get(f"{API}/summary?month=2026-10").json()
    assert (october["income_cents"], october["voucher_cents"]) == (15200, 15200)
    empty = client.get(f"{API}/summary?month=2026-09").json()
    assert empty["voucher_cents"] == 0

    trend = {m["month"]: m for m in client.get(f"{API}/summary/trend?month=2026-11&months=3").json()}
    assert trend["2026-11"]["voucher_cents"] == 16000 and trend["2026-11"]["income_cents"] == 201000
    assert trend["2026-10"]["voucher_cents"] == 15200
    assert trend["2026-09"]["voucher_cents"] == 0
    assert trend["2026-11"]["balance_cents"] == 201000 - 6400

    rows = list(csv.reader(io.StringIO(client.get(f"{API}/export/incomes.csv?month=2026-11").text)))
    assert [r[2] for r in rows[1:]] == ["Stipendio", "Buoni pasto"]

    # A monthly template for the vouchers, as for a salary.
    template = client.post(f"{API}/recurring-incomes", json={
        "amount": "160", "category": "meal_voucher", "interval_months": 1, "next_due": "2026-12-01",
    })
    assert template.status_code == 201 and template.json()["category_name"] == "Buoni pasto"


def test_income_summary_by_category(client, anon):
    users = users_of(client)
    make_income(client, amount="1850", income_date="2026-11-03")
    make_income(client, amount="1600", income_date="2026-11-03", received_by_user_id=users["Nastia"])
    make_income(client, amount="160", category="meal_voucher", income_date="2026-11-30")
    make_income(client, amount="50", category="gift", income_date="2026-11-14")
    make_income(client, amount="999", income_date="2026-10-27")    # other month

    summary = client.get(f"{API}/summary/incomes?month=2026-11").json()
    assert summary["month"] == "2026-11"
    assert summary["total_cents"] == 366000
    assert summary["income_count"] == 4
    assert [(c["category"], c["category_name"], c["total_cents"], c["income_count"]) for c in summary["by_category"]] == [
        ("salary", "Stipendio", 345000, 2),
        ("meal_voucher", "Buoni pasto", 16000, 1),
        ("gift", "Regali", 5000, 1),
    ]
    # The same total as the monthly summary.
    assert client.get(f"{API}/summary?month=2026-11").json()["income_cents"] == summary["total_cents"]

    empty = client.get(f"{API}/summary/incomes?month=2026-01").json()
    assert empty == {"month": "2026-01", "total_cents": 0, "income_count": 0, "by_category": []}
    assert client.get(f"{API}/summary/incomes?month=2026-13").status_code == 422
    assert client.get(f"{API}/summary/incomes").status_code == 422
    assert anon.get(f"{API}/summary/incomes?month=2026-11").status_code == 401
