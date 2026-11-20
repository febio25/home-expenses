"""Recurring income templates: create, register, skip, guards.

The same rules as the recurring expense templates (test_recurring.py).
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from tests.conftest import CSRF, NASTIA

API = "/api/v1"


def make_template(client, **overrides):
    body = {
        "amount": "1850",
        "category": "salary",
        "interval_months": 1,
        "next_due": "2026-11-27",
    }
    body.update(overrides)
    response = client.post(f"{API}/recurring-incomes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def users_of(client):
    return {u["display_name"]: u["id"] for u in client.get(f"{API}/users").json()}


def test_create_and_list(client):
    template = make_template(client, note="  netto ")
    assert template["amount_cents"] == 185000
    assert template["category"] == "salary" and template["category_name"] == "Stipendio"
    assert template["received_by_name"] == "Fabio"   # defaults to the logged-in user
    assert template["note"] == "netto"
    assert template["day_of_month"] == 27
    assert template["interval_months"] == 1
    assert template["is_active"] is True
    assert client.get(f"{API}/recurring-incomes").json() == [template]
    assert client.get(f"{API}/recurring-incomes/{template['id']}").json() == template
    # Expense templates are a separate list.
    assert client.get(f"{API}/recurring").json() == []


def test_list_order(client):
    later = make_template(client, next_due="2026-12-10")
    first = make_template(client, next_due="2026-11-27")
    paused = make_template(client, next_due="2026-11-01")
    client.patch(f"{API}/recurring-incomes/{paused['id']}", json={"is_active": False})
    ids = [t["id"] for t in client.get(f"{API}/recurring-incomes").json()]
    assert ids == [first["id"], later["id"], paused["id"]]


def test_register_with_template_values(client):
    users = users_of(client)
    template = make_template(client, received_by_user_id=users["Nastia"], note="Stipendio")
    response = client.post(
        f"{API}/recurring-incomes/{template['id']}/register", json={"due_date": "2026-11-27"}
    )
    assert response.status_code == 201, response.text
    income = response.json()["income"]
    assert income["amount_cents"] == 185000
    assert income["income_date"] == "2026-11-27"
    assert income["category_name"] == "Stipendio"
    assert income["received_by_name"] == "Nastia"
    assert income["created_by_name"] == "Fabio"
    assert income["note"] == "Stipendio"
    assert response.json()["recurring"]["next_due"] == "2026-12-27"
    assert [i["id"] for i in client.get(f"{API}/incomes").json()] == [income["id"]]
    # It counts in the summary like any other income.
    assert client.get(f"{API}/summary?month=2026-11").json()["income_cents"] == 185000


def test_register_with_changes(client):
    template = make_template(client, interval_months=1)
    response = client.post(
        f"{API}/recurring-incomes/{template['id']}/register",
        json={
            "due_date": "2026-11-27", "amount": "3.700,00", "income_date": "2026-11-26",
            "category": "other", "note": "Con tredicesima",
        },
    )
    assert response.status_code == 201, response.text
    income = response.json()["income"]
    assert income["amount_cents"] == 370000
    assert income["income_date"] == "2026-11-26"
    assert income["category"] == "other"
    assert income["note"] == "Con tredicesima"
    # The proposed amount of the template does not change.
    assert response.json()["recurring"]["amount_cents"] == 185000
    assert response.json()["recurring"]["category"] == "salary"


def test_second_registration_of_same_occurrence_is_refused(client):
    template = make_template(client)
    url = f"{API}/recurring-incomes/{template['id']}/register"
    assert client.post(url, json={"due_date": "2026-11-27"}).status_code == 201
    again = client.post(url, json={"due_date": "2026-11-27"})
    assert again.status_code == 409
    assert "già stata registrata" in again.json()["detail"]
    assert len(client.get(f"{API}/incomes").json()) == 1


def test_the_other_person_registered_it_first(client, app):
    template = make_template(client)
    with TestClient(app, headers=CSRF) as nastia:
        nastia.post(f"{API}/auth/login", json={"username": "Nastia", "password": NASTIA["password"]})
        assert nastia.post(
            f"{API}/recurring-incomes/{template['id']}/register", json={"due_date": "2026-11-27"}
        ).status_code == 201
    late = client.post(
        f"{API}/recurring-incomes/{template['id']}/register", json={"due_date": "2026-11-27"}
    )
    assert late.status_code == 409
    assert len(client.get(f"{API}/incomes").json()) == 1


def test_retry_with_same_client_uuid_is_idempotent(client):
    template = make_template(client)
    url = f"{API}/recurring-incomes/{template['id']}/register"
    body = {"due_date": "2026-11-27", "client_uuid": "retry-income-0001"}
    assert client.post(url, json=body).status_code == 201
    retry = client.post(url, json=body)
    assert retry.status_code == 200
    assert retry.json()["recurring"]["next_due"] == "2026-12-27"  # moved once only
    assert len(client.get(f"{API}/incomes").json()) == 1


def test_overdue_template_catches_up_one_period_at_a_time(client):
    template = make_template(client, next_due="2026-09-27")
    url = f"{API}/recurring-incomes/{template['id']}/register"
    assert client.post(url, json={"due_date": "2026-09-27"}).json()["recurring"]["next_due"] == "2026-10-27"
    skipped = client.post(
        f"{API}/recurring-incomes/{template['id']}/skip", json={"due_date": "2026-10-27"}
    )
    assert skipped.status_code == 200
    assert skipped.json()["next_due"] == "2026-11-27"
    assert len(client.get(f"{API}/incomes").json()) == 1
    # Skipping an occurrence that is not the current one is refused.
    stale = client.post(f"{API}/recurring-incomes/{template['id']}/skip", json={"due_date": "2026-10-27"})
    assert stale.status_code == 409


def test_suspended_template_cannot_be_registered_or_skipped(client):
    template = make_template(client)
    client.patch(f"{API}/recurring-incomes/{template['id']}", json={"is_active": False})
    for action in ("register", "skip"):
        response = client.post(
            f"{API}/recurring-incomes/{template['id']}/{action}", json={"due_date": "2026-11-27"}
        )
        assert response.status_code == 409, action
        assert response.json()["detail"] == "Questa entrata ricorrente è sospesa."


def test_future_occurrence_is_refused_like_any_income(client, pinned_today):
    template = make_template(client, next_due="2027-08-27")  # pinned today: 30/06/2027
    response = client.post(
        f"{API}/recurring-incomes/{template['id']}/register", json={"due_date": "2027-08-27"}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "La data non può essere nel futuro."
    assert client.get(f"{API}/recurring-incomes/{template['id']}").json()["next_due"] == "2027-08-27"


def test_update_and_clamped_day(client):
    template = make_template(client, next_due="2026-10-31", note="Piano")
    users = users_of(client)
    updated = client.patch(
        f"{API}/recurring-incomes/{template['id']}",
        json={
            "amount": "1.900,00", "category": "other", "note": None,
            "received_by_user_id": users["Nastia"], "interval_months": 3,
        },
    ).json()
    assert updated["amount_cents"] == 190000
    assert updated["category_name"] == "Altro"
    assert updated["note"] is None
    assert updated["received_by_name"] == "Nastia"
    assert updated["interval_months"] == 3

    registered = client.post(
        f"{API}/recurring-incomes/{template['id']}/register", json={"due_date": "2026-10-31"}
    ).json()["recurring"]
    assert registered["next_due"] == "2027-01-31"
    # "Annulla" in the app puts the date back; a clamped date keeps the day.
    month = client.patch(f"{API}/recurring-incomes/{template['id']}", json={"next_due": "2026-11-30"}).json()
    assert month["day_of_month"] == 31
    other = client.patch(f"{API}/recurring-incomes/{template['id']}", json={"next_due": "2026-12-15"}).json()
    assert other["day_of_month"] == 15

    for field in ("amount", "category", "received_by_user_id", "interval_months", "next_due", "is_active"):
        assert client.patch(f"{API}/recurring-incomes/{template['id']}", json={field: None}).status_code == 422, field
    assert client.patch(f"{API}/recurring-incomes/9999", json={"amount": "1"}).status_code == 404


def test_validation(client):
    base = {"amount": "1850", "category": "salary", "next_due": "2026-11-27"}
    post = lambda **extra: client.post(f"{API}/recurring-incomes", json={**base, **extra})  # noqa: E731
    assert post(interval_months=0).status_code == 422
    assert post(interval_months=13).status_code == 422
    assert post(interval_months=1, amount="0").status_code == 422
    assert post(interval_months=1, amount="1.850").status_code == 422  # ambiguous, as everywhere
    assert post(interval_months=1, category="bonus").status_code == 422
    assert post(interval_months=1, received_by_user_id=9999).status_code == 422
    assert post(interval_months=1).status_code == 201


def test_delete_template_keeps_incomes(client):
    template = make_template(client)
    client.post(f"{API}/recurring-incomes/{template['id']}/register", json={"due_date": "2026-11-27"})
    assert client.delete(f"{API}/recurring-incomes/{template['id']}").status_code == 204
    assert client.get(f"{API}/recurring-incomes").json() == []
    assert len(client.get(f"{API}/incomes").json()) == 1
    assert client.delete(f"{API}/recurring-incomes/{template['id']}").status_code == 404


def test_access_rules(client, anon, app):
    assert anon.get(f"{API}/recurring-incomes").status_code == 401
    template = make_template(client)
    with TestClient(app) as bare:  # cookie but no CSRF header
        bare.cookies.set("spese_session", client.cookies["spese_session"])
        assert bare.get(f"{API}/recurring-incomes").status_code == 200
        assert bare.post(
            f"{API}/recurring-incomes/{template['id']}/register", json={"due_date": "2026-11-27"}
        ).status_code == 403
    assert client.get(f"{API}/incomes").json() == []


def test_backup_restores_templates_and_old_backups_get_the_table(client, tmp_path):
    from app.config import get_settings
    from app.db import latest_schema_version

    template = make_template(client)
    backup = client.get(f"{API}/backup").content
    client.delete(f"{API}/recurring-incomes/{template['id']}")
    assert client.post(f"{API}/restore", content=backup).status_code == 200
    assert [t["id"] for t in client.get(f"{API}/recurring-incomes").json()] == [template["id"]]

    # A backup of 0.5.0 (schema 3) has no such table: it is created empty.
    old = tmp_path / "schema3.db"
    old.write_bytes(backup)
    conn = sqlite3.connect(old)
    conn.execute("DROP TABLE recurring_incomes")
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    conn.close()
    assert client.post(f"{API}/restore", content=old.read_bytes()).status_code == 200
    assert client.get(f"{API}/recurring-incomes").json() == []
    live = sqlite3.connect(get_settings().db_path)
    try:
        assert live.execute("PRAGMA user_version").fetchone()[0] == latest_schema_version()
    finally:
        live.close()
