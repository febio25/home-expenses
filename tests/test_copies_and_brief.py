"""0.14.0: copies of the database kept on the server (daily, before an
update, before a restore), the last backup download, and the files plus
text for an AI assistant ("Per Claude" in Impostazioni → Esporta CSV)."""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from tests.conftest import CSRF, NASTIA, make_expense
from tests.test_incomes import make_income

API = "/api/v1"


# --- daily copies ----------------------------------------------------------------------


def test_the_app_writes_todays_copy_when_it_starts(client, categories, tmp_path, pinned_today):
    # The client fixture started the app before the setup: no users, no copy
    # yet (an empty database is not worth it). The hourly check makes it
    # once there is something to keep: here, called directly.
    make_expense(client, categories)
    from app.copies import ensure_daily_copy

    path = ensure_daily_copy()
    assert path is not None and path.name == f"daily-{pinned_today.isoformat()}.db"
    assert ensure_daily_copy() is None  # once a day
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 1
    conn.close()
    listed = client.get(f"{API}/backups").json()["copies"]
    assert [(c["name"], c["kind"]) for c in listed] == [(path.name, "daily")]
    assert listed[0]["size_bytes"] > 0


def test_only_the_last_seven_daily_copies_stay(client, categories, tmp_path, monkeypatch):
    from datetime import date, timedelta

    import app.dates
    from app.copies import ensure_daily_copy

    make_expense(client, categories)
    start = date(2027, 6, 1)
    for offset in range(10):
        monkeypatch.setattr(app.dates, "today", lambda offset=offset: start + timedelta(days=offset))
        ensure_daily_copy()
    names = sorted(p.name for p in (tmp_path / "snapshots").glob("daily-*.db"))
    assert names == [f"daily-2027-06-{day:02d}.db" for day in range(4, 11)]


def test_no_copy_before_the_first_setup(anon, tmp_path):
    from app.copies import ensure_daily_copy

    assert ensure_daily_copy() is None
    assert not list(tmp_path.rglob("daily-*.db"))


# --- copy before an update -------------------------------------------------------------------


def test_an_update_that_changes_the_database_keeps_a_copy_first(client, categories, tmp_path, app):
    make_expense(client, categories)
    db_path = tmp_path / "spese.db"
    # Pretend the database comes from 0.11.0 (schema 8) with one migration to
    # come: drop nothing, just lower the version and add a fake migration.
    from app import db as db_module

    latest = db_module.latest_schema_version()
    conn = sqlite3.connect(db_path)
    conn.execute(f"PRAGMA user_version = {latest - 1}")
    conn.commit()
    conn.close()
    original = db_module.list_migrations
    db_module.list_migrations = lambda: [m for m in original() if m[0] < latest] + [
        (latest, _fake_migration(tmp_path))
    ]
    try:
        db_module.init_db()
    finally:
        db_module.list_migrations = original
    copies_found = list((tmp_path / "snapshots").glob(f"pre-update-v{latest - 1}-*.db"))
    assert len(copies_found) == 1
    conn = sqlite3.connect(copies_found[0])
    assert conn.execute("PRAGMA user_version").fetchone()[0] == latest - 1
    assert conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 1
    conn.close()
    kinds = [c["kind"] for c in client.get(f"{API}/backups").json()["copies"]]
    assert "pre_update" in kinds


def _fake_migration(tmp_path):
    path = tmp_path / "999_noop.sql"
    path.write_text("SELECT 1;", encoding="utf-8")
    return path


def test_no_copy_when_nothing_changes(client, categories, tmp_path):
    from app.db import init_db

    make_expense(client, categories)
    init_db()  # same version: nothing to migrate
    assert not list(tmp_path.rglob("pre-update-*.db"))


# --- restore from a copy ----------------------------------------------------------------------


def test_restore_from_a_copy_and_undo_it(client, categories, tmp_path):
    from app.copies import ensure_daily_copy

    make_expense(client, categories, merchant="Prima")
    daily = ensure_daily_copy()
    make_expense(client, categories, merchant="Dopo")
    assert len(client.get(f"{API}/expenses").json()) == 2

    response = client.post(f"{API}/backups/{daily.name}/restore")
    assert response.status_code == 200, response.text
    assert [e["merchant_name"] for e in client.get(f"{API}/expenses").json()] == ["Prima"]
    copies_listed = client.get(f"{API}/backups").json()["copies"]
    replaced = [c for c in copies_listed if c["kind"] == "pre_restore"]
    assert len(replaced) == 1
    assert daily.exists()  # the copy restored stays

    # The data replaced is itself a copy: restoring it undoes the restore.
    assert client.post(f"{API}/backups/{replaced[0]['name']}/restore").status_code == 200
    assert len(client.get(f"{API}/expenses").json()) == 2


def test_restoring_the_oldest_pre_restore_copy_does_not_delete_it_first(client, categories, tmp_path):
    from app.copies import ensure_daily_copy

    make_expense(client, categories)
    daily = ensure_daily_copy()
    for _ in range(3):
        assert client.post(f"{API}/backups/{daily.name}/restore").status_code == 200
    listed = [c["name"] for c in client.get(f"{API}/backups").json()["copies"] if c["kind"] == "pre_restore"]
    assert len(listed) == 3
    oldest = listed[-1]  # newest first
    assert client.post(f"{API}/backups/{oldest}/restore").status_code == 200
    after = [c["name"] for c in client.get(f"{API}/backups").json()["copies"] if c["kind"] == "pre_restore"]
    # The new copy came in, the oldest (just restored) went out after use.
    assert len(after) == 3
    assert after[1:] == listed[:2]
    assert oldest not in after


def test_only_listed_copies_can_be_restored(client, categories, tmp_path):
    make_expense(client, categories)
    (tmp_path / "snapshots").mkdir(exist_ok=True)
    for name in ("spese.db", "daily-2027-06-30.db", "daily-x.txt", "daily-..db"):
        assert client.post(f"{API}/backups/{name}/restore").status_code == 404
    # A path that leaves the folder never reaches the endpoint.
    assert client.post(f"{API}/backups/..%2Fspese.db/restore").status_code in (404, 405)
    (tmp_path / "snapshots" / "daily-2027-01-01.db").write_bytes(b"not a database")
    assert client.post(f"{API}/backups/daily-2027-01-01.db/restore").status_code == 422


def test_old_pre_restore_copies_move_in_with_the_others(app, tmp_path):
    (tmp_path / "pre-restore-20261120-101010.db").write_bytes(b"x")
    with TestClient(app):
        pass
    assert not list(tmp_path.glob("pre-restore-*.db"))
    assert (tmp_path / "snapshots" / "pre-restore-20261120-101010.db").exists()


def test_copies_need_a_login(anon):
    assert anon.get(f"{API}/backups").status_code == 401
    assert anon.post(f"{API}/backups/daily-2027-06-30.db/restore", headers=CSRF).status_code == 401


# --- last download -----------------------------------------------------------------------------


def test_last_backup_download_is_recorded_for_both_users(client, app, categories):
    assert client.get(f"{API}/backups").json()["last_download"] is None
    assert client.get(f"{API}/backup").status_code == 200
    last = client.get(f"{API}/backups").json()["last_download"]
    assert last["user_name"] == "Fabio"
    assert last["at"].endswith("Z")
    with TestClient(app, headers=CSRF) as nastia:
        nastia.post(f"{API}/auth/login", json={"username": "Nastia", "password": NASTIA["password"]})
        assert nastia.get(f"{API}/backups").json()["last_download"]["user_name"] == "Fabio"
        nastia.get(f"{API}/backup")
        assert nastia.get(f"{API}/backups").json()["last_download"]["user_name"] == "Nastia"


def test_backup_file_name_says_it_is_utc(client):
    disposition = client.get(f"{API}/backup").headers["content-disposition"]
    assert disposition.startswith('attachment; filename="spese-backup-')
    assert disposition.endswith('Z.db"')


# --- files and text for an AI assistant ----------------------------------------------------------


def test_brief_of_a_month(client, categories):
    make_expense(client, categories, amount="2.400,00", expense_date="2026-11-10")
    make_expense(client, categories, amount="25,54", expense_date="2026-11-12")
    make_expense(client, categories, amount="99", expense_date="2026-10-31")  # other month
    make_income(client, amount="3753,33", income_date="2026-11-27")
    make_income(client, amount="160", category="meal_voucher", income_date="2026-11-27")

    brief = client.get(f"{API}/export/brief", params={"month": "2026-11"}).json()
    assert brief["files"] == [
        {"name": "spese_2026-11.csv", "url": "/api/v1/export.csv?month=2026-11&format=standard"},
        {"name": "entrate_2026-11.csv", "url": "/api/v1/export/incomes.csv?month=2026-11&format=standard"},
    ]
    text = brief["text"]
    assert "novembre 2026" in text
    assert "spese_2026-11.csv: 2 spese, totale 2.425,54 €." in text
    assert "entrate_2026-11.csv: 2 entrate, totale 3.913,33 €, di cui 160,00 € in buoni pasto." in text
    assert "Entrate meno spese: +1.487,79 €." in text
    assert "«Buoni pasto»" in text and "«Vinted»" in text
    assert "data futura" not in text
    # The files listed are the ones the export gives, with the same rows.
    for file in brief["files"]:
        response = client.get(file["url"])
        assert response.status_code == 200
        assert file["name"] in response.headers["content-disposition"]
    assert len(client.get(brief["files"][0]["url"]).text.strip().splitlines()) == 3


def test_brief_of_a_range_with_planned_expenses_and_no_incomes(client, categories, pinned_today):
    make_expense(client, categories, amount="10", expense_date="2027-06-01")
    make_expense(client, categories, amount="55", expense_date="2027-07-15")  # after "today"
    brief = client.get(f"{API}/export/brief", params={"from": "2027-06-01", "to": "2027-07-31"}).json()
    assert [file["name"] for file in brief["files"]] == ["spese_2027-06-01_2027-07-31.csv"]
    text = brief["text"]
    assert "dal 1° giugno 2027 al 31 luglio 2027" in text
    assert "Nessuna entrata registrata nel periodo." in text
    assert "Entrate meno spese" not in text
    assert "1 spesa ha una data futura (55,00 € in tutto)" in text


def test_brief_with_nothing_to_export(client):
    brief = client.get(f"{API}/export/brief", params={"month": "2026-01"}).json()
    assert brief["files"] == []
    assert "Nessuna spesa registrata nel periodo." in brief["text"]


def test_brief_follows_a_renamed_vinted_category(client):
    vinted = next(c for c in client.get(f"{API}/categories").json() if c["system_key"] == "vinted")
    client.patch(f"{API}/categories/{vinted['id']}", json={"name": "Rivendite"})
    text = client.get(f"{API}/export/brief", params={"month": "2026-11"}).json()["text"]
    assert "Categoria «Rivendite» delle spese" in text


def test_euro_format_of_the_brief():
    from app.export_brief import euro

    assert euro(242554) == "2.425,54 €"
    assert euro(5) == "0,05 €"
    assert euro(-130210, signed=True) == "−1.302,10 €"
    assert euro(148779, signed=True) == "+1.487,79 €"
    assert euro(123456789) == "1.234.567,89 €"
