import csv
import io
import sqlite3

from fastapi.testclient import TestClient

from tests.conftest import CSRF, FABIO, make_expense

API = "/api/v1"
HEADER = [
    "data",
    "importo",
    "categoria",
    "esercente",
    "nota",
    "pagato_da",
    "metodo_pagamento",
    "inserito_da",
    "creato_il",
]


def _seed(client, categories):
    users = {u["display_name"]: u["id"] for u in client.get(f"{API}/users").json()}
    make_expense(
        client,
        categories,
        amount="1234,56",
        merchant="Ferramenta Rossi, Bianchi & C.",
        note='tubo "flessibile"; 2 pezzi',
        expense_date="2026-11-02",
        category_id=categories["Casa e utenze"],
    )
    make_expense(
        client,
        categories,
        amount="0,05",
        merchant="Caffè Città",
        expense_date="2026-11-01",
        paid_by_user_id=users["Nastia"],
        payment_method="cash",
        category_id=categories["Ristoranti e bar"],
    )
    make_expense(client, categories, amount="7", merchant=None, expense_date="2026-12-05")


def test_standard_csv(client, categories):
    _seed(client, categories)
    response = client.get(f"{API}/export.csv?month=2026-11")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="spese_2026-11.csv"' in response.headers["content-disposition"]
    assert not response.content.startswith(b"\xef\xbb\xbf")  # no BOM for parsers

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert rows[0] == HEADER
    assert len(rows) == 3  # header + the two November expenses, oldest first
    first, second = rows[1], rows[2]
    assert first[:8] == [
        "2026-11-01", "0.05", "Ristoranti e bar", "Caffè Città", "", "Nastia", "Contanti", "Fabio",
    ]
    assert second[:8] == [
        "2026-11-02",
        "1234.56",
        "Casa e utenze",
        "Ferramenta Rossi, Bianchi & C.",   # comma inside a field survives quoting
        'tubo "flessibile"; 2 pezzi',
        "Fabio",
        "Carta",
        "Fabio",
    ]
    # creato_il: ISO 8601 UTC timestamp
    assert len(first[8]) == 20 and first[8].endswith("Z") and first[8][10] == "T"


def test_excel_italian_csv(client, categories):
    _seed(client, categories)
    response = client.get(f"{API}/export.csv?month=2026-11&format=excel_it")
    assert response.content.startswith(b"\xef\xbb\xbf")  # BOM so Excel reads accents
    assert 'filename="spese_2026-11_excel.csv"' in response.headers["content-disposition"]

    text = response.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert rows[0] == HEADER
    assert rows[1][1] == "0,05"
    assert rows[2][1] == "1234,56"                       # decimal comma, no thousands separator
    assert rows[2][4] == 'tubo "flessibile"; 2 pezzi'    # semicolon inside a field survives
    assert rows[1][3] == "Caffè Città"


def test_export_by_range_and_all(client, categories):
    _seed(client, categories)
    ranged = client.get(f"{API}/export.csv?from=2026-11-02&to=2026-12-31")
    rows = list(csv.reader(io.StringIO(ranged.text)))
    assert [r[0] for r in rows[1:]] == ["2026-11-02", "2026-12-05"]
    assert rows[2][3] == ""  # no merchant -> empty field
    assert "spese_2026-11-02_2026-12-31.csv" in ranged.headers["content-disposition"]

    everything = client.get(f"{API}/export.csv")
    assert len(everything.text.strip().splitlines()) == 4

    empty = client.get(f"{API}/export.csv?month=2020-01")
    assert empty.text.strip() == ",".join(HEADER)

    assert client.get(f"{API}/export.csv?format=nope").status_code == 422


def test_backup_download_is_a_complete_database(client, categories, tmp_path):
    _seed(client, categories)
    response = client.get(f"{API}/backup")
    assert response.status_code == 200
    assert response.content.startswith(b"SQLite format 3\x00")
    assert "spese-backup-" in response.headers["content-disposition"]

    copy = tmp_path / "downloaded.db"
    copy.write_bytes(response.content)
    conn = sqlite3.connect(copy)
    assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()
    # The temporary snapshot is cleaned up after the download.
    assert not list(tmp_path.glob("backup-*.db"))


def test_backup_and_restore_round_trip(client, categories, tmp_path):
    _seed(client, categories)
    backup = client.get(f"{API}/backup").content
    before = client.get(f"{API}/expenses").json()

    # Change things after the backup...
    for expense in before:
        client.delete(f"{API}/expenses/{expense['id']}")
    client.post(f"{API}/categories", json={"name": "Dopo il backup"})
    assert client.get(f"{API}/expenses").json() == []

    # ...then restore.
    restored = client.post(
        f"{API}/restore", content=backup, headers={"Content-Type": "application/octet-stream"}
    )
    assert restored.status_code == 200, restored.text

    assert client.get(f"{API}/expenses").json() == before
    names = [c["name"] for c in client.get(f"{API}/categories").json()]
    assert "Dopo il backup" not in names
    # A safety copy of the replaced database is kept next to the live one.
    assert len(list(tmp_path.glob("pre-restore-*.db"))) == 1
    assert not list(tmp_path.glob("restore-*.db"))


def test_restore_into_a_fresh_install(client, categories, tmp_path_factory, monkeypatch):
    _seed(client, categories)
    backup = client.get(f"{API}/backup").content

    # A brand-new installation with different users.
    fresh_dir = tmp_path_factory.mktemp("fresh")
    monkeypatch.setenv("SPESE_DATA_DIR", str(fresh_dir))
    from app.main import create_app

    with TestClient(create_app(), headers=CSRF) as fresh:
        fresh.post(f"{API}/setup", json={"users": [{"name": "Temp", "password": "temp-password"}]})
        fresh.post(f"{API}/auth/login", json={"username": "Temp", "password": "temp-password"})
        assert fresh.post(f"{API}/restore", content=backup).status_code == 200

        # The temporary user is gone with its session; the original users are back.
        assert fresh.get(f"{API}/auth/me").status_code == 401
        login = fresh.post(
            f"{API}/auth/login", json={"username": "Fabio", "password": FABIO["password"]}
        )
        assert login.status_code == 200
        assert len(fresh.get(f"{API}/expenses").json()) == 3


def test_restore_rejects_bad_files(client, categories, tmp_path):
    make_expense(client, categories)

    def restore(payload):
        return client.post(f"{API}/restore", content=payload)

    assert restore(b"").status_code == 422
    assert restore(b"this is not a database").status_code == 422
    assert restore(b"SQLite format 3\x00" + b"\x00" * 200).status_code == 422

    # A valid SQLite file that is not ours.
    other = tmp_path / "other.db"
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
    conn.commit()
    conn.close()
    assert restore(other.read_bytes()).status_code == 422

    # A backup "from the future" (newer schema than this app knows).
    future = tmp_path / "future.db"
    future.write_bytes(client.get(f"{API}/backup").content)
    conn = sqlite3.connect(future)
    conn.execute("PRAGMA user_version = 999")
    conn.commit()
    conn.close()
    assert restore(future.read_bytes()).status_code == 422

    # Nothing was touched by the failed attempts.
    assert len(client.get(f"{API}/expenses").json()) == 1
    assert not list(tmp_path.glob("pre-restore-*.db"))


def test_data_survives_a_restart(app, tmp_path):
    with TestClient(app, headers=CSRF) as first:
        first.post(f"{API}/setup", json={"users": [FABIO]})
        first.post(f"{API}/auth/login", json={"username": "Fabio", "password": FABIO["password"]})
        categories = {c["name"]: c["id"] for c in first.get(f"{API}/categories").json()}
        make_expense(first, categories)
        token = first.cookies["spese_session"]

    from app.main import create_app

    with TestClient(create_app(), headers=CSRF) as second:  # same data dir, new process
        second.cookies.set("spese_session", token)
        assert second.get(f"{API}/auth/me").status_code == 200  # session persisted too
        assert len(second.get(f"{API}/expenses").json()) == 1
        assert len(second.get(f"{API}/categories").json()) == 11  # seed and Vinted not duplicated
