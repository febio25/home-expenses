"""Vinted (0.10.0): items not on Vinted yet ("Da pubblicare"), the day they
are published, and the update of a 0.9.0 database (schema 5), whose items
all had a date."""

from __future__ import annotations

from app import db as app_db
from app.routers.vinted import ITEM_SELECT, item_out
from tests.conftest import PINNED_TODAY
from tests.test_vinted import API, JPEG, THUMB, b64, bought, make_item, sell


def patch(client, item_id, **body):
    return client.patch(f"{API}/vinted/items/{item_id}", json=body)


def test_publish_change_the_day_and_unpublish(client):
    item = make_item(client, title="Giacca jeans", purchase=bought(day="2026-11-02"))
    assert (item["status"], item["listed_on"]) == ("unlisted", None)

    published = patch(client, item["id"], listed_on=PINNED_TODAY.isoformat())
    assert published.status_code == 200
    assert (published.json()["status"], published.json()["listed_on"]) == ("listed", PINNED_TODAY.isoformat())

    moved = patch(client, item["id"], listed_on="2026-11-02").json()  # same day as the purchase: fine
    assert moved["listed_on"] == "2026-11-02"

    back = patch(client, item["id"], listed_on=None).json()
    assert (back["status"], back["listed_on"]) == ("unlisted", None)
    # Title and note untouched by the date.
    assert back["title"] == "Giacca jeans"


def test_publication_day_validation(client):
    item = make_item(client, purchase=bought(day="2026-11-02"))

    def detail(day):
        response = patch(client, item["id"], listed_on=day)
        assert response.status_code == 422, response.text
        return response.json()["detail"]

    assert detail("2026-11-01") == "La data di pubblicazione non può essere prima dell'acquisto."
    assert detail("2027-08-01") == "La data non può essere nel futuro."
    assert detail("1999-12-31") == "Data non valida: deve essere dal 2000 in poi."
    assert patch(client, item["id"], listed_on="ieri").status_code == 422
    assert client.get(f"{API}/vinted/items/{item['id']}").json()["listed_on"] is None  # nothing saved

    sold = sell(client, item["id"], day="2026-11-18")
    assert detail("2026-11-19") == "La data di pubblicazione non può essere dopo la vendita."
    assert patch(client, item["id"], listed_on="2026-11-18").json()["listed_on"] == "2026-11-18"
    # A sold item can lose its date (sold without being published): still sold.
    cleared = patch(client, item["id"], listed_on=None).json()
    assert (cleared["status"], cleared["listed_on"]) == ("sold", None)
    assert sold["gain_cents"] == cleared["gain_cents"]

    own = make_item(client, title="Zaino")  # already at home: no purchase to compare with
    assert patch(client, own["id"], listed_on="2001-03-04").json()["listed_on"] == "2001-03-04"
    assert patch(client, 999, listed_on="2026-11-02").status_code == 404


def test_sold_or_withdrawn_before_publication(client):
    item = make_item(client, title="Libro")
    sold = sell(client, item["id"], "8", "2026-11-20")
    assert (sold["status"], sold["listed_on"], sold["gain_cents"]) == ("sold", None, 800)
    assert client.delete(f"{API}/vinted/items/{item['id']}/sale").status_code == 204
    assert client.get(f"{API}/vinted/items/{item['id']}").json()["status"] == "unlisted"

    withdrawn = patch(client, item["id"], is_withdrawn=True).json()
    assert withdrawn["status"] == "withdrawn"
    # Withdrawing again undone: back where it was, not on Vinted yet.
    assert patch(client, item["id"], is_withdrawn=False).json()["status"] == "unlisted"

    listed = make_item(client, title="Stivali", listed_on="2026-11-03")
    patch(client, listed["id"], is_withdrawn=True)
    assert patch(client, listed["id"], is_withdrawn=False).json()["status"] == "listed"


def test_unlisted_filter_and_order(client):
    old = make_item(client, title="Comprato prima", purchase=bought(day="2026-10-05"))
    home = make_item(client, title="Di casa")  # added "today" (UTC day of created_at)
    recent = make_item(client, title="Comprato dopo", purchase=bought(day="2026-11-10"))
    on_sale = make_item(client, title="In vendita", listed_on="2026-11-12")

    unlisted = client.get(f"{API}/vinted/items?status=unlisted").json()
    # Newest first: by purchase, else by the day the item was added (the
    # real clock's day, after November 2026).
    assert [i["id"] for i in unlisted] == [home["id"], recent["id"], old["id"]]
    assert [i["id"] for i in client.get(f"{API}/vinted/items?status=listed").json()] == [on_sale["id"]]
    assert len(client.get(f"{API}/vinted/items").json()) == 4


def test_summary_and_trend_do_not_depend_on_publication(client):
    # The money lives in expenses and incomes: publishing changes no total.
    item = make_item(client, purchase=bought("10", "2026-11-02"))
    before = client.get(f"{API}/vinted/summary?month=2026-11").json()
    patch(client, item["id"], listed_on="2026-11-05")
    assert client.get(f"{API}/vinted/summary?month=2026-11").json() == before


def test_backup_and_restore_keep_the_publication_state(client):
    waiting = make_item(client, title="Gonna", purchase=bought())
    published = make_item(client, title="Felpa", listed_on="2026-11-06")
    client.put(f"{API}/vinted/items/{waiting['id']}/photo", json={"image": b64(JPEG), "thumb": b64(THUMB)})
    backup = client.get(f"{API}/backup").content

    patch(client, waiting["id"], listed_on="2026-11-07")
    patch(client, published["id"], listed_on=None)
    assert client.post(f"{API}/restore", content=backup).status_code == 200

    restored = {i["title"]: i for i in client.get(f"{API}/vinted/items").json()}
    assert (restored["Gonna"]["status"], restored["Gonna"]["listed_on"]) == ("unlisted", None)
    assert (restored["Felpa"]["status"], restored["Felpa"]["listed_on"]) == ("listed", "2026-11-06")
    assert client.get(f"{API}/vinted/items/{waiting['id']}/photo").content == JPEG


def test_update_from_schema_5_keeps_dates_and_photos(tmp_path):
    """A 0.9.0 database: listed_on NOT NULL, every item with a date. The
    migration must keep the dates (items stay "In vendita") and the photos,
    which a rebuilt table would have deleted through ON DELETE CASCADE."""
    conn = app_db.connect(tmp_path / "spese.db")
    for version, path in app_db.list_migrations():
        if version > 5:
            break
        conn.executescript(f"BEGIN;\n{path.read_text(encoding='utf-8')}\nPRAGMA user_version = {version};\nCOMMIT;")
    now = "2026-11-20T10:00:00Z"
    conn.execute(
        "INSERT INTO users (id, username, display_name, password_hash, created_at)"
        " VALUES (1, 'nastia', 'Nastia', 'x', ?)",
        (now,),
    )
    conn.executemany(
        "INSERT INTO vinted_items (id, title, listed_on, is_withdrawn, created_by_user_id, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, 1, ?, ?)",
        [(1, "Borsa", "2026-11-02", 0, now, now), (2, "Stivali", "2026-10-08", 1, now, now)],
    )
    conn.execute(
        "INSERT INTO vinted_photos (item_id, token, created_at, image, thumb) VALUES (1, 'abc', ?, ?, ?)",
        (now, JPEG, THUMB),
    )
    conn.commit()

    app_db.migrate(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == app_db.latest_schema_version()
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    items = {row["title"]: item_out(row) for row in conn.execute(f"{ITEM_SELECT} ORDER BY v.id")}
    assert (items["Borsa"]["status"], items["Borsa"]["listed_on"], items["Borsa"]["photo"]) == (
        "listed", "2026-11-02", "abc")
    assert (items["Stivali"]["status"], items["Stivali"]["listed_on"]) == ("withdrawn", "2026-10-08")
    photo = conn.execute("SELECT image, thumb FROM vinted_photos WHERE item_id = 1").fetchone()
    assert (photo["image"], photo["thumb"]) == (JPEG, THUMB)
    # The date is optional now.
    conn.execute("UPDATE vinted_items SET listed_on = NULL WHERE id = 1")
    assert item_out(conn.execute(f"{ITEM_SELECT} WHERE v.id = 1").fetchone())["status"] == "unlisted"
    # Running the migrations again changes nothing.
    app_db.migrate(conn)
    conn.close()
