"""Shared fixtures: a fresh app and database for every test."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

FABIO = {"name": "Fabio", "password": "password-fabio"}
NASTIA = {"name": "Nastia", "password": "password-nastia"}
CSRF = {"X-Requested-With": "spese"}


# Tests use dates around November 2026. Pinning "today" keeps the
# "no future expenses" rule from breaking them as the calendar moves on.
PINNED_TODAY = date(2027, 6, 30)


@pytest.fixture(autouse=True)
def pinned_today(monkeypatch):
    import app.dates

    monkeypatch.setattr(app.dates, "today", lambda: PINNED_TODAY)
    return PINNED_TODAY


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SPESE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SPESE_COOKIE_SECURE", "false")  # TestClient speaks plain HTTP
    from app.main import create_app

    return create_app()


@pytest.fixture
def anon(app):
    """Client with no session."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(app):
    """Client logged in as Fabio, with both users created."""
    with TestClient(app, headers=CSRF) as client:
        response = client.post("/api/v1/setup", json={"users": [FABIO, NASTIA]})
        assert response.status_code == 201, response.text
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "Fabio", "password": FABIO["password"]},
        )
        assert response.status_code == 200, response.text
        yield client


@pytest.fixture
def categories(client):
    """Category name -> id."""
    return {c["name"]: c["id"] for c in client.get("/api/v1/categories").json()}


def strip_recurring_variable(conn):
    """Undo migration 010 on a copy of a backup, to simulate one made
    before 0.17.0."""
    for table in ("recurring_expenses", "recurring_incomes"):
        # a test simulating an even older backup may have dropped the table already
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
        if "is_variable" in columns:
            conn.execute(f"ALTER TABLE {table} DROP COLUMN is_variable")


def strip_category_icons(conn):
    """Undo migration 009 on a copy of a backup, to simulate one made
    before 0.15.0 (and what came after it: 0.17.0, variable amounts)."""
    strip_recurring_variable(conn)
    conn.execute("ALTER TABLE categories DROP COLUMN icon")


def strip_merchant_pairs(conn):
    """Undo migration 008 on a copy of a backup, to simulate one made
    before 0.11.0 (and what came after it: 0.15.0, the category icons)."""
    strip_category_icons(conn)
    conn.execute("DROP TABLE merchant_distinct_pairs")


def strip_vinted_schema(conn):
    """Undo migration 005 on a copy of a backup, to simulate one made before
    0.8.0. The "Vinted" category row stays: the migration adopts it again by
    name, as it does with a category created by hand. Also drops what came
    after 0.8.0 on top of it (0.10.0: the price history of the listings;
    0.11.0: the merchants marked as not duplicates)."""
    strip_merchant_pairs(conn)
    conn.execute("DROP TABLE vinted_price_changes")
    conn.execute("DROP TABLE vinted_photos")
    conn.execute("DROP TABLE vinted_items")
    conn.execute("DROP INDEX idx_categories_system_key")
    conn.execute("ALTER TABLE categories DROP COLUMN system_key")


def make_expense(client, categories, **overrides):
    body = {
        "amount": "12,50",
        "category_id": categories["Spesa alimentare"],
        "merchant": "Lidl",
        "expense_date": "2026-11-13",
    }
    body.update(overrides)
    response = client.post("/api/v1/expenses", json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()
