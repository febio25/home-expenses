from tests.conftest import make_expense

API = "/api/v1"

INITIAL = [
    "Spesa alimentare",
    "Casa e utenze",
    "Salute",
    "Auto e trasporti",
    "Ristoranti e bar",
    "Abbigliamento",
    "Svago",
    "Abbonamenti",
    "Regali",
    "Varie",
]


def test_initial_categories(client):
    names = [c["name"] for c in client.get(f"{API}/categories").json()]
    assert names == INITIAL


def test_add_rename_deactivate(client, categories):
    created = client.post(f"{API}/categories", json={"name": "  Animali  "})
    assert created.status_code == 201
    assert created.json()["name"] == "Animali"
    assert client.get(f"{API}/categories").json()[-1]["name"] == "Animali"  # appended last

    duplicate = client.post(f"{API}/categories", json={"name": "animali"})
    assert duplicate.status_code == 409

    renamed = client.patch(f"{API}/categories/{categories['Varie']}", json={"name": "Altro"})
    assert renamed.json()["name"] == "Altro"
    clash = client.patch(f"{API}/categories/{categories['Svago']}", json={"name": "ALTRO"})
    assert clash.status_code == 409

    client.patch(f"{API}/categories/{categories['Svago']}", json={"is_active": False})
    active = [c["name"] for c in client.get(f"{API}/categories").json()]
    assert "Svago" not in active
    everything = client.get(f"{API}/categories?include_inactive=true").json()
    assert any(c["name"] == "Svago" and not c["is_active"] for c in everything)


def test_renaming_a_category_keeps_its_expenses(client, categories):
    expense = make_expense(client, categories)
    client.patch(f"{API}/categories/{categories['Spesa alimentare']}", json={"name": "Cibo"})
    assert client.get(f"{API}/expenses/{expense['id']}").json()["category_name"] == "Cibo"


def test_used_category_cannot_be_deleted(client, categories):
    make_expense(client, categories)
    used = client.delete(f"{API}/categories/{categories['Spesa alimentare']}")
    assert used.status_code == 409
    unused = client.delete(f"{API}/categories/{categories['Regali']}")
    assert unused.status_code == 204


def test_last_active_category_cannot_be_deactivated(client, categories):
    ids = list(categories.values())
    for category_id in ids[:-1]:
        ok = client.patch(f"{API}/categories/{category_id}", json={"is_active": False})
        assert ok.status_code == 200
    last = client.patch(f"{API}/categories/{ids[-1]}", json={"is_active": False})
    assert last.status_code == 409


def test_merchant_suggests_its_last_category(client, categories):
    make_expense(client, categories, merchant="Esselunga", category_id=categories["Varie"])
    make_expense(client, categories, merchant="Esselunga", category_id=categories["Spesa alimentare"])
    merchant = client.get(f"{API}/merchants").json()[0]
    assert merchant["last_category_id"] == categories["Spesa alimentare"]

    # A deactivated category is no longer suggested; fall back to the previous one.
    client.patch(f"{API}/categories/{categories['Spesa alimentare']}", json={"is_active": False})
    merchant = client.get(f"{API}/merchants").json()[0]
    assert merchant["last_category_id"] == categories["Varie"]


def test_merchants_are_listed_most_used_first(client, categories):
    make_expense(client, categories, merchant="Bar Sport")
    make_expense(client, categories, merchant="Lidl")
    make_expense(client, categories, merchant="Lidl")
    assert [m["name"] for m in client.get(f"{API}/merchants").json()] == ["Lidl", "Bar Sport"]


def test_rename_merchant(client, categories):
    expense = make_expense(client, categories, merchant="Lidl Via Roma")
    make_expense(client, categories, merchant="Lidl")
    merchants = {m["name"]: m["id"] for m in client.get(f"{API}/merchants").json()}

    renamed = client.patch(f"{API}/merchants/{merchants['Lidl Via Roma']}", json={"name": "Lidl Roma"})
    assert renamed.status_code == 200
    assert client.get(f"{API}/expenses/{expense['id']}").json()["merchant_name"] == "Lidl Roma"

    # Fixing only the capitalisation of a merchant is a rename, not a clash.
    recased = client.patch(f"{API}/merchants/{merchants['Lidl']}", json={"name": "LIDL"})
    assert recased.status_code == 200

    clash = client.patch(f"{API}/merchants/{merchants['Lidl Via Roma']}", json={"name": "lidl"})
    assert clash.status_code == 409


def test_merge_merchants(client, categories):
    a = make_expense(client, categories, merchant="Lidl Via Roma", amount="1")
    b = make_expense(client, categories, merchant="Lidl", amount="2")
    merchants = {m["name"]: m["id"] for m in client.get(f"{API}/merchants").json()}

    merged = client.post(
        f"{API}/merchants/{merchants['Lidl Via Roma']}/merge", json={"into_id": merchants["Lidl"]}
    )
    assert merged.status_code == 200
    assert merged.json()["expense_count"] == 2
    assert [m["name"] for m in client.get(f"{API}/merchants").json()] == ["Lidl"]
    for expense in (a, b):
        assert client.get(f"{API}/expenses/{expense['id']}").json()["merchant_name"] == "Lidl"

    itself = client.post(
        f"{API}/merchants/{merchants['Lidl']}/merge", json={"into_id": merchants["Lidl"]}
    )
    assert itself.status_code == 422
    missing = client.post(f"{API}/merchants/{merchants['Lidl']}/merge", json={"into_id": 999})
    assert missing.status_code == 404
