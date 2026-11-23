"""Limits on expense dates: up to a year ahead, nothing before 2000."""

from __future__ import annotations

from datetime import timedelta

from tests.conftest import PINNED_TODAY, make_expense
from tests.test_vinted import bought, make_item

API = "/api/v1"


def body(categories, expense_date):
    return {"amount": "5", "category_id": categories["Varie"], "expense_date": expense_date}


def test_today_and_tomorrow_are_accepted(client, categories):
    # Tomorrow is tolerated: the server clock is UTC, the phones are ahead.
    for day in (PINNED_TODAY, PINNED_TODAY + timedelta(days=1)):
        response = client.post(f"{API}/expenses", json=body(categories, day.isoformat()))
        assert response.status_code == 201, response.text


def test_planned_expense_is_accepted_up_to_twelve_months_ahead(client, categories):
    # Pinned today: 2027-06-30. The server allows a day more than the phone
    # (UTC), so the last day is 2028-07-01.
    for day in ("2027-07-02", "2027-12-28", "2028-07-01"):
        response = client.post(f"{API}/expenses", json=body(categories, day))
        assert response.status_code == 201, response.text
        assert response.json()["expense_date"] == day


def test_date_beyond_twelve_months_is_rejected(client, categories):
    for day in ("2028-07-02", "2062-01-01"):
        response = client.post(f"{API}/expenses", json=body(categories, day))
        assert response.status_code == 422
        assert response.json()["detail"] == "La data non può essere oltre 12 mesi da oggi."
    assert client.get(f"{API}/expenses").json() == []


def test_planned_expense_counts_in_its_own_month_only(client, categories):
    client.post(f"{API}/expenses", json={**body(categories, "2027-12-28"), "amount": "49,90"})
    december = client.get(f"{API}/expenses?month=2027-12").json()
    assert [item["amount_cents"] for item in december] == [4990]
    assert client.get(f"{API}/expenses?month=2027-11").json() == []
    assert client.get(f"{API}/summary?month=2027-12").json()["total_cents"] == 4990
    trend = client.get(f"{API}/summary/trend?month=2027-12&months=2").json()
    assert [item["expense_cents"] for item in trend] == [0, 4990]
    csv_text = client.get(f"{API}/export.csv?month=2027-12").text
    assert "2027-12-28,49.90," in csv_text


def test_date_before_2000_is_rejected(client, categories):
    for day in ("1999-12-31", "0001-01-01"):
        response = client.post(f"{API}/expenses", json=body(categories, day))
        assert response.status_code == 422
        assert "2000" in response.json()["detail"]
    assert client.post(f"{API}/expenses", json=body(categories, "2000-01-01")).status_code == 201


def test_edit_can_plan_an_expense_but_not_beyond_twelve_months(client, categories):
    expense = make_expense(client, categories)
    url = f"{API}/expenses/{expense['id']}"
    planned = (PINNED_TODAY + timedelta(days=30)).isoformat()
    assert client.patch(url, json={"expense_date": planned}).status_code == 200
    assert client.get(url).json()["expense_date"] == planned
    response = client.patch(url, json={"expense_date": "2028-07-02"})
    assert response.status_code == 422
    assert client.get(url).json()["expense_date"] == planned


def test_the_purchase_of_a_vinted_item_cannot_be_planned(client):
    item = make_item(client, purchase=bought(day="2027-06-01"))
    expense_id = item["purchase"]["expense_id"]
    day = (PINNED_TODAY + timedelta(days=10)).isoformat()
    response = client.patch(f"{API}/expenses/{expense_id}", json={"expense_date": day})
    assert response.status_code == 422
    assert response.json()["detail"] == "La data non può essere nel futuro."


def test_incomes_stay_limited_to_today(client):
    day = (PINNED_TODAY + timedelta(days=10)).isoformat()
    response = client.post(f"{API}/incomes", json={"amount": "100", "category": "other", "income_date": day})
    assert response.status_code == 422
    assert response.json()["detail"] == "La data non può essere nel futuro."


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
