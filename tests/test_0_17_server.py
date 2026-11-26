"""0.17.0: variable amounts of the recurring items, their monthly and yearly
cost, the login that takes the same time for any name."""

from __future__ import annotations

import sqlite3

from app.config import get_settings
from app.db import latest_schema_version
from tests.conftest import FABIO, strip_recurring_variable

API = "/api/v1"


def expense_template(client, categories, **overrides):
    body = {"amount": "10", "category_id": categories["Casa e utenze"], "merchant": "Enel",
            "interval_months": 1, "next_due": "2026-12-05"}
    body.update(overrides)
    response = client.post(f"{API}/recurring", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def income_template(client, **overrides):
    body = {"amount": "1850", "category": "salary", "interval_months": 1, "next_due": "2026-12-27"}
    body.update(overrides)
    response = client.post(f"{API}/recurring-incomes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


# --- «Importo variabile» --------------------------------------------------------------


def test_variable_amount_for_expenses(client, categories):
    fixed = expense_template(client, categories)
    assert fixed["is_variable"] is False
    bill = expense_template(client, categories, amount="140", is_variable=True)
    assert bill["is_variable"] is True
    changed = client.patch(f"{API}/recurring/{bill['id']}", json={"is_variable": False}).json()
    assert changed["is_variable"] is False
    assert client.patch(f"{API}/recurring/{bill['id']}", json={"is_variable": None}).status_code == 422
    listed = {t["id"]: t["is_variable"] for t in client.get(f"{API}/recurring").json()}
    assert listed == {fixed["id"]: False, bill["id"]: False}


def test_variable_amount_for_incomes(client):
    salary = income_template(client, is_variable=True)
    assert salary["is_variable"] is True
    changed = client.patch(f"{API}/recurring-incomes/{salary['id']}", json={"is_variable": False}).json()
    assert changed["is_variable"] is False
    assert client.get(f"{API}/recurring-incomes/{salary['id']}").json()["is_variable"] is False


def test_registering_a_variable_item_still_takes_the_amount_typed(client, categories):
    bill = expense_template(client, categories, amount="140", is_variable=True, next_due="2026-11-20")
    response = client.post(f"{API}/recurring/{bill['id']}/register",
                           json={"due_date": "2026-11-20", "amount": "152,30"})
    assert response.status_code == 201, response.text
    assert response.json()["expense"]["amount_cents"] == 15230
    # The template keeps its estimate.
    assert response.json()["recurring"]["amount_cents"] == 14000


# --- «Quanto costano» -------------------------------------------------------------------


def test_costs_a_month_and_a_year(client, categories):
    empty = client.get(f"{API}/summary/recurring").json()
    assert empty == {
        "expenses": {"count": 0, "month_cents": 0, "year_cents": 0, "has_variable": False},
        "incomes": {"count": 0, "month_cents": 0, "year_cents": 0, "has_variable": False},
    }
    expense_template(client, categories, amount="12")                      # 12,00 a month
    expense_template(client, categories, amount="24", interval_months=12)  # 2,00 a month
    expense_template(client, categories, amount="10", interval_months=3)   # 3,333… a month
    expense_template(client, categories, amount="10", interval_months=3)   # together 6,666…
    expense_template(client, categories, amount="10", interval_months=3)   # all three: 10,00
    paused = expense_template(client, categories, amount="999")
    client.patch(f"{API}/recurring/{paused['id']}", json={"is_active": False})
    income_template(client, amount="2100")
    income_template(client, amount="600", interval_months=6, is_variable=True)
    costs = client.get(f"{API}/summary/recurring").json()
    # 12 + 2 + 3 × 10/3 = 24,00 a month exactly (no 23,99 from rounding each one)
    assert costs["expenses"] == {"count": 5, "month_cents": 2400, "year_cents": 28800, "has_variable": False}
    assert costs["incomes"] == {"count": 2, "month_cents": 220000, "year_cents": 2640000, "has_variable": True}


def test_costs_round_to_the_cent(client, categories):
    expense_template(client, categories, amount="10", interval_months=3)
    costs = client.get(f"{API}/summary/recurring").json()["expenses"]
    assert costs["month_cents"] == 333 and costs["year_cents"] == 4000
    expense_template(client, categories, amount="0,05", interval_months=2, is_variable=True)
    costs = client.get(f"{API}/summary/recurring").json()["expenses"]
    assert costs["month_cents"] == 336 and costs["year_cents"] == 4030  # 1000/3 + 5/2 = 335,8…
    assert costs["has_variable"] is True


def test_costs_need_a_session(anon):
    assert anon.get(f"{API}/summary/recurring").status_code == 401


# --- migration 010 --------------------------------------------------------------------


def test_backup_of_016_gets_the_column(client, categories, tmp_path):
    template = expense_template(client, categories)
    income_template(client)
    old = tmp_path / "schema9.db"
    old.write_bytes(client.get(f"{API}/backup").content)
    conn = sqlite3.connect(old)
    strip_recurring_variable(conn)
    conn.execute("PRAGMA user_version = 9")
    conn.commit()
    conn.close()
    response = client.post(f"{API}/restore", content=old.read_bytes(),
                           headers={"Content-Type": "application/octet-stream"})
    assert response.status_code == 200, response.text
    restored = client.get(f"{API}/recurring/{template['id']}").json()
    assert restored["is_variable"] is False and restored["amount_cents"] == 1000
    assert [t["is_variable"] for t in client.get(f"{API}/recurring-incomes").json()] == [False]
    live = sqlite3.connect(get_settings().db_path)
    try:
        assert live.execute("PRAGMA user_version").fetchone()[0] == latest_schema_version() == 10
        assert live.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        live.close()


# --- login --------------------------------------------------------------------------------


def test_unknown_name_does_the_work_of_a_password_check(anon, client, monkeypatch):
    import app.routers.auth as auth

    calls = []
    real = auth.spend_password_time
    monkeypatch.setattr(auth, "spend_password_time", lambda password: calls.append(password) or real(password))
    response = anon.post(f"{API}/auth/login", json={"username": "Nessuno", "password": "qualcosa-di-lungo"},
                         headers={"X-Requested-With": "x"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Nome o password non corretti."
    assert calls == ["qualcosa-di-lungo"]
    # A known name with a wrong password: the real check only, same answer.
    response = anon.post(f"{API}/auth/login", json={"username": "Fabio", "password": "sbagliata-123"},
                         headers={"X-Requested-With": "x"})
    assert response.status_code == 401 and response.json()["detail"] == "Nome o password non corretti."
    assert calls == ["qualcosa-di-lungo"]
    response = anon.post(f"{API}/auth/login", json={"username": "Fabio", "password": FABIO["password"]},
                         headers={"X-Requested-With": "x"})
    assert response.status_code == 200
