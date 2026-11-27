"""Recurring expense templates: create, register, skip, guards."""

from __future__ import annotations

from datetime import date

from app.dates import add_months

from .conftest import make_expense

API = "/api/v1"


def make_template(client, categories, **overrides):
    body = {
        "amount": "13,99",
        "category_id": categories["Abbonamenti"],
        "merchant": "Netflix",
        "interval_months": 1,
        "next_due": "2026-11-05",
    }
    body.update(overrides)
    response = client.post(f"{API}/recurring", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_add_months_clamps_and_restores_the_day():
    assert add_months(date(2026, 1, 31), 1, 31) == date(2026, 2, 28)
    assert add_months(date(2026, 2, 28), 1, 31) == date(2026, 3, 31)
    assert add_months(date(2026, 11, 5), 2, 5) == date(2027, 1, 5)
    assert add_months(date(2028, 1, 29), 1, 29) == date(2028, 2, 29)
    assert add_months(date(2026, 3, 15), 12, 15) == date(2027, 3, 15)


def test_create_and_list(client, categories):
    template = make_template(client, categories)
    assert template["amount_cents"] == 1399
    assert template["merchant_name"] == "Netflix"
    assert template["paid_by_name"] == "Fabio"
    assert template["day_of_month"] == 5
    assert template["is_active"] is True
    assert [t["id"] for t in client.get(f"{API}/recurring").json()] == [template["id"]]


def test_register_with_template_values(client, categories):
    template = make_template(client, categories)
    response = client.post(
        f"{API}/recurring/{template['id']}/register", json={"due_date": "2026-11-05"}
    )
    assert response.status_code == 201, response.text
    expense = response.json()["expense"]
    assert expense["amount_cents"] == 1399
    assert expense["expense_date"] == "2026-11-05"
    assert expense["merchant_name"] == "Netflix"
    assert expense["category_name"] == "Abbonamenti"
    assert response.json()["recurring"]["next_due"] == "2026-12-05"
    assert len(client.get(f"{API}/expenses").json()) == 1


def test_register_with_a_different_amount(client, categories):
    template = make_template(client, categories, merchant="Enel", interval_months=2)
    response = client.post(
        f"{API}/recurring/{template['id']}/register",
        json={"due_date": "2026-11-05", "amount": "87,40", "expense_date": "2026-11-07"},
    )
    assert response.status_code == 201
    assert response.json()["expense"]["amount_cents"] == 8740
    assert response.json()["expense"]["expense_date"] == "2026-11-07"
    assert response.json()["recurring"]["next_due"] == "2027-01-05"
    # The proposed amount of the template does not change.
    assert response.json()["recurring"]["amount_cents"] == 1399


def test_second_registration_of_same_occurrence_is_refused(client, categories):
    template = make_template(client, categories)
    url = f"{API}/recurring/{template['id']}/register"
    assert client.post(url, json={"due_date": "2026-11-05"}).status_code == 201
    again = client.post(url, json={"due_date": "2026-11-05"})
    assert again.status_code == 409
    assert len(client.get(f"{API}/expenses").json()) == 1


def test_retry_with_same_client_uuid_is_idempotent(client, categories):
    template = make_template(client, categories)
    url = f"{API}/recurring/{template['id']}/register"
    body = {"due_date": "2026-11-05", "client_uuid": "retry-uuid-0001"}
    assert client.post(url, json=body).status_code == 201
    retry = client.post(url, json=body)
    assert retry.status_code == 200
    assert retry.json()["recurring"]["next_due"] == "2026-12-05"  # moved once only
    assert len(client.get(f"{API}/expenses").json()) == 1


def test_overdue_template_catches_up_one_period_at_a_time(client, categories):
    template = make_template(client, categories, next_due="2026-09-05")
    url = f"{API}/recurring/{template['id']}/register"
    assert client.post(url, json={"due_date": "2026-09-05"}).json()["recurring"]["next_due"] == "2026-10-05"
    skipped = client.post(f"{API}/recurring/{template['id']}/skip", json={"due_date": "2026-10-05"})
    assert skipped.status_code == 200
    assert skipped.json()["next_due"] == "2026-11-05"
    assert len(client.get(f"{API}/expenses").json()) == 1


def test_suspended_template_cannot_be_registered(client, categories):
    template = make_template(client, categories)
    client.patch(f"{API}/recurring/{template['id']}", json={"is_active": False})
    response = client.post(
        f"{API}/recurring/{template['id']}/register", json={"due_date": "2026-11-05"}
    )
    assert response.status_code == 409


def test_update_next_due_sets_day_and_clears_fields(client, categories):
    template = make_template(client, categories, note="Piano famiglia")
    updated = client.patch(
        f"{API}/recurring/{template['id']}",
        json={"next_due": "2026-11-30", "note": None, "merchant": None, "amount": "17,99"},
    ).json()
    assert updated["day_of_month"] == 30
    assert updated["note"] is None and updated["merchant_name"] is None
    assert updated["amount_cents"] == 1799


def test_inactive_category_must_be_replaced(client, categories):
    template = make_template(client, categories)
    client.patch(f"{API}/categories/{categories['Abbonamenti']}", json={"is_active": False})
    url = f"{API}/recurring/{template['id']}/register"
    assert client.post(url, json={"due_date": "2026-11-05"}).status_code == 409
    ok = client.post(url, json={"due_date": "2026-11-05", "category_id": categories["Svago"]})
    assert ok.status_code == 201


def test_category_used_by_template_cannot_be_deleted(client, categories):
    created = client.post(f"{API}/categories", json={"name": "Palestra"}).json()
    make_template(client, categories, category_id=created["id"])
    assert client.delete(f"{API}/categories/{created['id']}").status_code == 409


def test_merchant_rename_and_merge_follow_into_templates(client, categories):
    template = make_template(client, categories)
    expense = make_expense(client, categories, merchant="Netflix")
    client.patch(f"{API}/merchants/{expense['merchant_id']}", json={"name": "Netflix Italia"})
    assert client.get(f"{API}/recurring/{template['id']}").json()["merchant_name"] == "Netflix Italia"

    other = make_expense(client, categories, merchant="NFLX")
    client.post(f"{API}/merchants/{expense['merchant_id']}/merge", json={"into_id": other["merchant_id"]})
    assert client.get(f"{API}/recurring/{template['id']}").json()["merchant_name"] == "NFLX"


def test_delete_template_keeps_expenses(client, categories):
    template = make_template(client, categories)
    client.post(f"{API}/recurring/{template['id']}/register", json={"due_date": "2026-11-05"})
    assert client.delete(f"{API}/recurring/{template['id']}").status_code == 204
    assert client.get(f"{API}/recurring").json() == []
    assert len(client.get(f"{API}/expenses").json()) == 1


def test_validation(client, categories):
    bad = {"amount": "13,99", "category_id": categories["Abbonamenti"], "next_due": "2026-11-05"}
    assert client.post(f"{API}/recurring", json={**bad, "interval_months": 0}).status_code == 422
    assert client.post(f"{API}/recurring", json={**bad, "interval_months": 13}).status_code == 422
    assert client.post(f"{API}/recurring", json={**bad, "interval_months": 1, "amount": "0"}).status_code == 422


def test_requires_login(anon):
    assert anon.get(f"{API}/recurring").status_code == 401


def test_moving_back_to_a_clamped_date_keeps_the_day(client, categories):
    template = make_template(client, categories, next_due="2026-10-31")
    registered = client.post(
        f"{API}/recurring/{template['id']}/register", json={"due_date": "2026-10-31"}
    ).json()["recurring"]
    assert registered["next_due"] == "2026-11-30"
    # Undo in the app: the next due date goes back, the day stays 31.
    back = client.patch(f"{API}/recurring/{template['id']}", json={"next_due": "2026-11-30"}).json()
    assert back["day_of_month"] == 31


def test_restore_of_a_v010_backup_gets_the_new_table(client, tmp_path):
    """A backup made by v0.1.x (schema 1) restores and is migrated to the
    latest schema (recurring templates in 2, incomes in 3, recurring incomes in 4,
    Vinted items in 5)."""
    import sqlite3
    from pathlib import Path

    import app
    from app.config import get_settings
    from app.db import latest_schema_version
    from app.security import hash_password

    old = tmp_path / "old.db"
    conn = sqlite3.connect(old)
    conn.executescript((Path(app.__file__).parent / "migrations" / "001_init.sql").read_text())
    conn.execute(
        "INSERT INTO users (username, display_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("fabio", "Fabio", hash_password("password-fabio"), "2026-11-01T00:00:00Z"),
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()

    response = client.post(
        f"{API}/restore", content=old.read_bytes(), headers={"Content-Type": "application/octet-stream"}
    )
    assert response.status_code == 200, response.text
    live = sqlite3.connect(get_settings().db_path)
    try:
        assert live.execute("PRAGMA user_version").fetchone()[0] == latest_schema_version() == 11
        for table in ("recurring_expenses", "incomes", "recurring_incomes", "vinted_items", "vinted_photos",
                      "vinted_price_changes", "merchant_distinct_pairs"):
            assert live.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
        assert live.execute(
            "SELECT name FROM categories WHERE system_key = 'vinted'"
        ).fetchall() == [("Vinted",)]
        # 0.15.0: the initial categories and Vinted get their icons.
        icons = dict(live.execute("SELECT name, icon FROM categories").fetchall())
        assert icons["Spesa alimentare"] == "shopping-cart" and icons["Vinted"] == "hanger"
    finally:
        live.close()
