"""Possible duplicate merchants and «Non sono doppioni» (0.11.0)."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.merchant_duplicates import name_key, one_edit_apart, reason_for
from tests.conftest import CSRF, NASTIA, make_expense, strip_merchant_pairs

API = "/api/v1"


def reason(a: str, b: str) -> str | None:
    return reason_for(name_key(a), name_key(b))


@pytest.mark.parametrize("a, b", [
    # Same name, written differently.
    ("Lidl", "LIDL S.r.l."),
    ("Caffè Roma", "Caffe' Roma"),
    ("Mc Donald's", "McDonalds"),
    ("Esselunga spa", "Esselunga S.p.A."),
    ("Bar-Centrale", "Bar Centrale"),
])
def test_same_name_written_differently(a, b):
    assert reason(a, b) == "same"


def test_one_name_inside_the_other():
    assert reason("Lidl", "Lidl via Roma") == "contained"
    assert reason("Lidl via Roma", "Lidl") == "contained"
    assert reason("Coop", "Coop Lombardia") == "contained"
    assert reason("Esselunga", "Supermercato Esselunga Viale Monza") == "contained"
    # Whole words only, and the shorter name at least 4 letters.
    assert reason("Bar", "Bar Centrale") is None
    assert reason("Lid", "Lidl via Roma") is None
    assert reason("Roma", "Caffè Roma") == "contained"  # still offered: «Non sono doppioni» exists for this


def test_names_one_letter_apart():
    assert reason("Esselunga", "Eselunga") == "similar"      # a letter missing
    assert reason("Esselunga", "Esselungaa") == "similar"    # one more
    assert reason("Esselunga", "Esselunca") == "similar"     # one changed
    assert reason("Esselunga", "Esselugna") == "similar"     # two swapped
    assert reason("Farmacia Centrale", "Farmacia Cetrale") == "similar"
    # Short names are left alone: "Lidl" / "Lild" would catch too much.
    assert reason("Lidl", "Lild") is None
    assert reason("Conad", "Coand") is None
    assert reason("Esselunga", "Eselunca") is None            # two letters
    assert reason("Ikea", "Lidl") is None


def test_name_key_and_edit_distance():
    assert name_key("  LIDL  S.r.l. ").compact == "lidl"
    assert name_key("Spa").compact == "spa"  # a name made only of a company form stays
    assert name_key("Terme Spa").words == ("terme",)
    assert name_key("Caffè Né").words == ("caffe", "ne")
    assert one_edit_apart("abc", "abc") is False
    assert one_edit_apart("abcdef", "abcdefg") and one_edit_apart("abcdefg", "abcdef")
    assert one_edit_apart("abcdef", "bacdef") and one_edit_apart("abcdef", "abcdfe")
    assert not one_edit_apart("abcdef", "bcadef")
    assert reason("!!!", "???") is None  # nothing left to compare


def duplicates(client):
    response = client.get(f"{API}/merchants/duplicates")
    assert response.status_code == 200, response.text
    return [(pair["reason"], [m["name"] for m in pair["merchants"]]) for pair in response.json()]


def merchant_ids(client):
    return {m["name"]: m["id"] for m in client.get(f"{API}/merchants").json()}


@pytest.fixture
def several(client, categories):
    for name, count in [("Lidl", 3), ("Lidl via Roma", 1), ("LIDL S.r.l.", 1), ("Esselunga", 2),
                        ("Eselunga", 1), ("Bar", 1), ("Bar Centrale", 1)]:
        for _ in range(count):
            make_expense(client, categories, merchant=name)
    return merchant_ids(client)


def test_list_of_possible_duplicates(client, several):
    pairs = duplicates(client)
    assert pairs == [
        ("same", ["Lidl", "LIDL S.r.l."]),                # the one with more expenses first
        ("contained", ["Lidl", "Lidl via Roma"]),
        ("contained", ["Lidl via Roma", "LIDL S.r.l."]),  # as many expenses: the older first
        ("similar", ["Esselunga", "Eselunga"]),
    ]
    first = client.get(f"{API}/merchants/duplicates").json()[0]
    assert first["reason_name"] == "Stesso nome scritto in modo diverso"
    assert set(first["merchants"][0]) == {
        "id", "name", "expense_count", "recent_count", "last_category_id",  # recent_count: 0.14.0
    }
    assert first["merchants"][0]["expense_count"] == 3


def test_not_duplicates_is_remembered_for_both(client, several, app):
    ids = several
    response = client.post(f"{API}/merchants/{ids['Lidl via Roma']}/distinct", json={"other_id": ids["Lidl"]})
    assert response.status_code == 204, response.text
    # Twice, or in the other order: nothing changes.
    assert client.post(f"{API}/merchants/{ids['Lidl']}/distinct",
                       json={"other_id": ids["Lidl via Roma"]}).status_code == 204
    expected = [
        ("same", ["Lidl", "LIDL S.r.l."]),
        ("contained", ["Lidl via Roma", "LIDL S.r.l."]),
        ("similar", ["Esselunga", "Eselunga"]),
    ]
    assert duplicates(client) == expected
    with TestClient(app, headers=CSRF) as nastia:
        nastia.post(f"{API}/auth/login", json={"username": "Nastia", "password": NASTIA["password"]})
        assert duplicates(nastia) == expected

    # Undo: the pair is offered again.
    assert client.delete(f"{API}/merchants/{ids['Lidl']}/distinct/{ids['Lidl via Roma']}").status_code == 204
    assert ("contained", ["Lidl", "Lidl via Roma"]) in duplicates(client)
    assert client.delete(f"{API}/merchants/{ids['Lidl']}/distinct/{ids['Lidl via Roma']}").status_code == 204


def test_not_duplicates_validation(client, several):
    ids = several
    same = client.post(f"{API}/merchants/{ids['Lidl']}/distinct", json={"other_id": ids["Lidl"]})
    assert (same.status_code, same.json()["detail"]) == (422, "Scegli un esercente diverso.")
    missing = client.post(f"{API}/merchants/{ids['Lidl']}/distinct", json={"other_id": 999})
    assert (missing.status_code, missing.json()["detail"]) == (404, "Esercente non trovato.")
    assert client.post(f"{API}/merchants/999/distinct", json={"other_id": ids["Lidl"]}).status_code == 404
    assert client.post(f"{API}/merchants/{ids['Lidl']}/distinct", json={}).status_code == 422


def test_merge_from_a_pair_and_pairs_of_removed_merchants(client, categories, several):
    ids = several
    client.post(f"{API}/merchants/{ids['Lidl via Roma']}/distinct", json={"other_id": ids["Lidl"]})
    # «Unisci» on the first pair: "LIDL S.r.l." goes into "Lidl".
    merged = client.post(f"{API}/merchants/{ids['LIDL S.r.l.']}/merge", json={"into_id": ids["Lidl"]})
    assert merged.status_code == 200 and merged.json()["expense_count"] == 4
    assert duplicates(client) == [("similar", ["Esselunga", "Eselunga"])]

    # A merchant left without expenses disappears, and so do its pairs.
    client.post(f"{API}/merchants/{ids['Eselunga']}/distinct", json={"other_id": ids["Esselunga"]})
    expense = next(e for e in client.get(f"{API}/expenses").json() if e["merchant_name"] == "Lidl via Roma")
    assert client.delete(f"{API}/expenses/{expense['id']}").status_code == 204
    from app.config import get_settings

    live = sqlite3.connect(get_settings().db_path)
    try:
        rows = live.execute("SELECT merchant_a_id, merchant_b_id FROM merchant_distinct_pairs").fetchall()
    finally:
        live.close()
    assert rows == [tuple(sorted((ids["Esselunga"], ids["Eselunga"])))]


def test_cookie_writes_need_the_csrf_header(app, client, several):
    ids = several
    with TestClient(app) as bare:  # same database, no X-Requested-With
        bare.post(f"{API}/auth/login", json={"username": "Fabio", "password": "password-fabio"})
        refused = bare.post(f"{API}/merchants/{ids['Lidl']}/distinct", json={"other_id": ids["Bar"]})
        assert refused.status_code == 403
        assert bare.get(f"{API}/merchants/duplicates").status_code == 200


def test_backup_and_restore_keep_the_pairs(client, several, tmp_path):
    from app.config import get_settings
    from app.db import latest_schema_version

    ids = several
    client.post(f"{API}/merchants/{ids['Eselunga']}/distinct", json={"other_id": ids["Esselunga"]})
    backup = client.get(f"{API}/backup").content
    client.delete(f"{API}/merchants/{ids['Eselunga']}/distinct/{ids['Esselunga']}")
    restored = client.post(f"{API}/restore", content=backup,
                           headers={"Content-Type": "application/octet-stream"})
    assert restored.status_code == 200, restored.text
    assert ("similar", ["Esselunga", "Eselunga"]) not in duplicates(client)

    # A backup of 0.10.0 (schema 7) restores and gets the table, empty.
    old = tmp_path / "schema7.db"
    old.write_bytes(backup)
    conn = sqlite3.connect(old)
    strip_merchant_pairs(conn)
    conn.execute("PRAGMA user_version = 7")
    conn.commit()
    conn.close()
    response = client.post(f"{API}/restore", content=old.read_bytes(),
                           headers={"Content-Type": "application/octet-stream"})
    assert response.status_code == 200, response.text
    live = sqlite3.connect(get_settings().db_path)
    try:
        assert live.execute("PRAGMA user_version").fetchone()[0] == latest_schema_version() == 8
        assert live.execute("SELECT COUNT(*) FROM merchant_distinct_pairs").fetchone()[0] == 0
        assert live.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        live.close()
    assert ("similar", ["Esselunga", "Eselunga"]) in duplicates(client)
