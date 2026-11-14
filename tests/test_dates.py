"""Limits on expense dates: no future dates, nothing before 2000."""

from __future__ import annotations

from datetime import timedelta

from tests.conftest import PINNED_TODAY, make_expense

API = "/api/v1"


def body(categories, expense_date):
    return {"amount": "5", "category_id": categories["Varie"], "expense_date": expense_date}


def test_today_and_tomorrow_are_accepted(client, categories):
    # Tomorrow is tolerated: the server clock is UTC, the phones are ahead.
    for day in (PINNED_TODAY, PINNED_TODAY + timedelta(days=1)):
        response = client.post(f"{API}/expenses", json=body(categories, day.isoformat()))
        assert response.status_code == 201, response.text


def test_future_date_is_rejected(client, categories):
    day = (PINNED_TODAY + timedelta(days=2)).isoformat()
    response = client.post(f"{API}/expenses", json=body(categories, day))
    assert response.status_code == 422
    assert response.json()["detail"] == "La data non può essere nel futuro."


def test_date_before_2000_is_rejected(client, categories):
    for day in ("1999-12-31", "0001-01-01"):
        response = client.post(f"{API}/expenses", json=body(categories, day))
        assert response.status_code == 422
        assert "2000" in response.json()["detail"]
    assert client.post(f"{API}/expenses", json=body(categories, "2000-01-01")).status_code == 201


def test_edit_cannot_move_an_expense_into_the_future(client, categories):
    expense = make_expense(client, categories)
    day = (PINNED_TODAY + timedelta(days=30)).isoformat()
    response = client.patch(f"{API}/expenses/{expense['id']}", json={"expense_date": day})
    assert response.status_code == 422
    assert client.get(f"{API}/expenses/{expense['id']}").json()["expense_date"] == "2026-11-13"


def test_recurring_registration_checks_the_date(client, categories):
    template = client.post(f"{API}/recurring", json={
        "amount": "9,99", "category_id": categories["Abbonamenti"], "merchant": "Spotify",
        "interval_months": 1, "next_due": "2026-11-05",
    }).json()
    day = (PINNED_TODAY + timedelta(days=5)).isoformat()
    response = client.post(f"{API}/recurring/{template['id']}/register",
                           json={"due_date": "2026-11-05", "expense_date": day})
    assert response.status_code == 422
    # Nothing moved: the occurrence is still due.
    assert client.get(f"{API}/recurring/{template['id']}").json()["next_due"] == "2026-11-05"


def test_recurring_template_may_start_in_the_future(client, categories):
    # A template's next due date is not an expense date.
    day = (PINNED_TODAY + timedelta(days=200)).isoformat()
    response = client.post(f"{API}/recurring", json={
        "amount": "480", "category_id": categories["Auto e trasporti"], "merchant": "Assicurazione",
        "interval_months": 12, "next_due": day,
    })
    assert response.status_code == 201, response.text
