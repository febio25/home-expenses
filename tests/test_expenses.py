from fastapi.testclient import TestClient

from tests.conftest import CSRF, NASTIA, make_expense

API = "/api/v1"


def test_create_and_read(client, categories):
    expense = make_expense(client, categories, note="  settimanale ")
    assert expense["amount_cents"] == 1250
    assert expense["category_name"] == "Spesa alimentare"
    assert expense["merchant_name"] == "Lidl"
    assert expense["note"] == "settimanale"
    assert expense["paid_by_name"] == "Fabio"       # defaults to the logged-in user
    assert expense["created_by_name"] == "Fabio"
    assert expense["payment_method"] == "card"
    assert expense["expense_date"] == "2026-11-13"

    fetched = client.get(f"{API}/expenses/{expense['id']}").json()
    assert fetched == expense


def test_amount_is_validated(client, categories):
    for bad in ("", "abc", "0", "-3", "12,345"):
        response = client.post(
            f"{API}/expenses",
            json={
                "amount": bad,
                "category_id": categories["Varie"],
                "expense_date": "2026-11-13",
            },
        )
        assert response.status_code == 422, bad
        assert isinstance(response.json()["detail"], str)


def test_category_must_exist_and_be_active(client, categories):
    body = {"amount": "5", "category_id": 9999, "expense_date": "2026-11-13"}
    assert client.post(f"{API}/expenses", json=body).status_code == 422

    client.patch(f"{API}/categories/{categories['Svago']}", json={"is_active": False})
    body["category_id"] = categories["Svago"]
    assert client.post(f"{API}/expenses", json=body).status_code == 422


def test_merchant_is_optional(client, categories):
    expense = make_expense(client, categories, merchant=None)
    assert expense["merchant_id"] is None
    blank = make_expense(client, categories, merchant="   ")
    assert blank["merchant_id"] is None


def test_merchants_match_ignoring_case_and_spaces(client, categories):
    first = make_expense(client, categories, merchant="Lidl")
    second = make_expense(client, categories, merchant="  LIDL ")
    third = make_expense(client, categories, merchant="lidl")
    assert first["merchant_id"] == second["merchant_id"] == third["merchant_id"]
    merchants = client.get(f"{API}/merchants").json()
    assert [(m["name"], m["expense_count"]) for m in merchants] == [("Lidl", 3)]


def test_retry_with_same_client_uuid_does_not_duplicate(client, categories):
    body = {
        "amount": "30",
        "category_id": categories["Varie"],
        "expense_date": "2026-11-13",
        "client_uuid": "0b7d4c1e-9a52-4f0e-8a55-3f1f7d0c2a11",
    }
    first = client.post(f"{API}/expenses", json=body)
    retry = client.post(f"{API}/expenses", json=body)
    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    assert len(client.get(f"{API}/expenses").json()) == 1


def test_list_by_month_and_range(client, categories):
    make_expense(client, categories, expense_date="2026-10-31", amount="1")
    make_expense(client, categories, expense_date="2026-11-01", amount="2")
    make_expense(client, categories, expense_date="2026-11-30", amount="3")
    make_expense(client, categories, expense_date="2026-12-01", amount="4")

    november = client.get(f"{API}/expenses?month=2026-11").json()
    assert [e["amount_cents"] for e in november] == [300, 200]  # newest first

    ranged = client.get(f"{API}/expenses?from=2026-10-31&to=2026-11-01").json()
    assert sorted(e["amount_cents"] for e in ranged) == [100, 200]

    assert len(client.get(f"{API}/expenses").json()) == 4
    assert client.get(f"{API}/expenses?month=2026-13").status_code == 422
    assert client.get(f"{API}/expenses?from=2026-12-01&to=2026-11-01").status_code == 422


def test_list_by_category(client, categories):
    food, gifts = categories["Spesa alimentare"], categories["Regali"]
    make_expense(client, categories, category_id=food, expense_date="2026-10-31", amount="1")
    make_expense(client, categories, category_id=food, expense_date="2026-11-02", amount="2")
    make_expense(client, categories, category_id=food, expense_date="2026-11-20", amount="3")
    make_expense(client, categories, category_id=gifts, expense_date="2026-11-10", amount="4")

    # Combined with the month: what makes up a category total in the summary.
    november_food = client.get(f"{API}/expenses?month=2026-11&category_id={food}").json()
    assert [e["amount_cents"] for e in november_food] == [300, 200]  # newest first
    summary = client.get(f"{API}/summary?month=2026-11").json()
    food_total = next(c for c in summary["by_category"] if c["category_id"] == food)
    assert food_total["total_cents"] == sum(e["amount_cents"] for e in november_food)

    # On its own, and with a date range.
    assert len(client.get(f"{API}/expenses?category_id={food}").json()) == 3
    ranged = client.get(f"{API}/expenses?from=2026-11-01&to=2026-11-15&category_id={food}").json()
    assert [e["amount_cents"] for e in ranged] == [200]

    # A deactivated category still lists its expenses; an unknown one lists nothing.
    client.patch(f"{API}/categories/{gifts}", json={"is_active": False})
    assert len(client.get(f"{API}/expenses?category_id={gifts}").json()) == 1
    assert client.get(f"{API}/expenses?category_id=9999").json() == []
    assert client.get(f"{API}/expenses?category_id=abc").status_code == 422


def test_february_in_a_leap_year(client, categories):
    make_expense(client, categories, expense_date="2024-02-29")
    assert len(client.get(f"{API}/expenses?month=2024-02").json()) == 1


def test_update(client, categories):
    expense = make_expense(client, categories)
    users = {u["display_name"]: u["id"] for u in client.get(f"{API}/users").json()}
    updated = client.patch(
        f"{API}/expenses/{expense['id']}",
        json={
            "amount": "99,99",
            "category_id": categories["Regali"],
            "merchant": "Feltrinelli",
            "paid_by_user_id": users["Nastia"],
            "payment_method": "cash",
            "expense_date": "2026-11-10",
            "note": "libro",
        },
    ).json()
    assert updated["amount_cents"] == 9999
    assert updated["category_name"] == "Regali"
    assert updated["merchant_name"] == "Feltrinelli"
    assert updated["paid_by_name"] == "Nastia"
    assert updated["created_by_name"] == "Fabio"
    assert updated["payment_method"] == "cash"
    assert updated["expense_date"] == "2026-11-10"
    assert updated["note"] == "libro"
    # The merchant nobody uses anymore is gone from the autocomplete.
    assert [m["name"] for m in client.get(f"{API}/merchants").json()] == ["Feltrinelli"]


def test_partial_update_leaves_other_fields_alone(client, categories):
    expense = make_expense(client, categories, note="nota")
    updated = client.patch(f"{API}/expenses/{expense['id']}", json={"amount": "1"}).json()
    assert updated["amount_cents"] == 100
    assert updated["merchant_name"] == "Lidl"
    assert updated["note"] == "nota"

    cleared = client.patch(
        f"{API}/expenses/{expense['id']}", json={"merchant": None, "note": None}
    ).json()
    assert cleared["merchant_id"] is None
    assert cleared["note"] is None


def test_an_old_expense_can_keep_its_deactivated_category(client, categories):
    expense = make_expense(client, categories, category_id=categories["Svago"])
    client.patch(f"{API}/categories/{categories['Svago']}", json={"is_active": False})
    same = client.patch(
        f"{API}/expenses/{expense['id']}",
        json={"amount": "8", "category_id": categories["Svago"]},
    )
    assert same.status_code == 200


def test_delete(client, categories):
    expense = make_expense(client, categories)
    assert client.delete(f"{API}/expenses/{expense['id']}").status_code == 204
    assert client.get(f"{API}/expenses/{expense['id']}").status_code == 404
    assert client.delete(f"{API}/expenses/{expense['id']}").status_code == 404
    assert client.get(f"{API}/merchants").json() == []


def test_both_users_see_and_edit_the_same_data(client, categories, app):
    expense = make_expense(client, categories)
    with TestClient(app, headers=CSRF) as nastia:
        login = nastia.post(
            f"{API}/auth/login", json={"username": "Nastia", "password": NASTIA["password"]}
        )
        assert login.status_code == 200
        assert [e["id"] for e in nastia.get(f"{API}/expenses").json()] == [expense["id"]]

        hers = make_expense(nastia, categories, merchant="Farmacia", amount="8,40")
        assert hers["paid_by_name"] == "Nastia"
        assert hers["created_by_name"] == "Nastia"
        edited = nastia.patch(f"{API}/expenses/{expense['id']}", json={"amount": "13"})
        assert edited.status_code == 200
    assert len(client.get(f"{API}/expenses").json()) == 2
    assert client.get(f"{API}/expenses/{expense['id']}").json()["amount_cents"] == 1300


def test_summary(client, categories):
    make_expense(client, categories, amount="10", category_id=categories["Spesa alimentare"])
    make_expense(client, categories, amount="5,50", category_id=categories["Spesa alimentare"])
    make_expense(client, categories, amount="40", category_id=categories["Salute"])
    make_expense(client, categories, amount="999", expense_date="2026-10-01")

    summary = client.get(f"{API}/summary?month=2026-11").json()
    assert summary["total_cents"] == 5550
    assert summary["expense_count"] == 3
    assert [(c["category_name"], c["total_cents"]) for c in summary["by_category"]] == [
        ("Salute", 4000),
        ("Spesa alimentare", 1550),
    ]
    empty = client.get(f"{API}/summary?month=2025-01").json()
    assert empty["total_cents"] == 0 and empty["by_category"] == []
    assert client.get(f"{API}/summary").status_code == 422
