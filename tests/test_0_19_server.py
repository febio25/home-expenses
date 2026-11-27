"""0.19.0 (F7): the markdown of the Vinted items on sale. Today is pinned
to 30 June 2027 (tests/conftest.py)."""

from __future__ import annotations

import sqlite3

from app.config import get_settings
from app.vinted_listing import AT_MINIMUM, parse_answer
from app.vinted_markdown import next_price, parse_plan, steps_ahead
from tests.conftest import strip_vinted_markdown
from tests.test_vinted import API, make_item, sell
from tests.test_vinted_listing import patch, request_text

BASE = {"kind": "pct", "amount": 10, "days": 14}


def markdown(client, item_id):
    return client.get(f"{API}/vinted/items/{item_id}").json()["markdown"]


# --- the rules ------------------------------------------------------------------------------


def test_plans_in_words():
    assert parse_plan("10% ogni 14 giorni") == BASE
    assert parse_plan("**2 € ogni 7 giorni**") == {"kind": "eur", "amount": 200, "days": 7}
    assert parse_plan("1,50 euro ogni 2 settimane") == {"kind": "eur", "amount": 150, "days": 14}
    assert parse_plan("5% ogni settimana") == {"kind": "pct", "amount": 5, "days": 7}
    assert parse_plan("Niente, è un pezzo raro") == {"kind": "none", "amount": None, "days": None}
    for unreadable in ("5 ogni 10 giorni", "10%", "60% ogni 14 giorni", "10% ogni 100 giorni",
                       "0,20 € ogni 7 giorni", "7,5% ogni 14 giorni", "", None, "dipende"):
        assert parse_plan(unreadable) is None, unreadable


def test_steps_round_down_to_half_a_euro_and_stop_at_the_minimum():
    assert next_price(3500, 2500, BASE) == 3150
    assert steps_ahead(3500, 2500, BASE) == [3150, 2800, 2500]
    assert steps_ahead(800, 600, BASE) == [700, 600]  # 7,20 → 7,00
    assert steps_ahead(300, 100, BASE) == [250, 200, 150, 100]  # always at least 0,50 less
    assert steps_ahead(4500, 3000, {"kind": "eur", "amount": 500, "days": 10}) == [4000, 3500, 3000]
    assert steps_ahead(2500, 2500, BASE) == []


# --- where an item stands -------------------------------------------------------------------


def test_base_plan_from_the_day_of_publication(client):
    due = make_item(client, title="Giacca", listed_on="2027-06-01", price="35", min_price="25")
    state = due["markdown"]
    assert state["plan"] == {"kind": "pct", "amount": 10, "days": 14, "source": "base",
                             "text": "−10% ogni 14 giorni"}
    assert (state["state"], state["since"], state["due_on"]) == ("due", "2027-06-01", "2027-06-15")
    assert (state["next_price_cents"], state["steps"]) == (3150, [3150, 2800, 2500])

    waiting = make_item(client, title="Borsa", listed_on="2027-06-20", price="35", min_price="25")
    assert (waiting["markdown"]["state"], waiting["markdown"]["due_on"]) == ("waiting", "2027-07-04")

    # «Ribassa a 31,50 €»: the price changed on Vinted, the round starts again today.
    lowered = patch(client, due["id"], price="31,50")["markdown"]
    assert (lowered["state"], lowered["since"], lowered["due_on"]) == ("waiting", "2027-06-30", "2027-07-14")
    assert lowered["steps"] == [2800, 2500]


def test_skip_puts_the_step_off_by_a_round(client):
    item = make_item(client, title="Giacca", listed_on="2027-06-01", price="35", min_price="25")
    response = client.post(f"{API}/vinted/items/{item['id']}/markdown/skip")
    assert response.status_code == 200, response.text
    state = response.json()["markdown"]
    assert (state["state"], state["due_on"], state["since"]) == ("waiting", "2027-07-14", "2027-06-01")
    assert response.json()["listing"]["price_cents"] == 3500
    assert client.post(f"{API}/vinted/items/{item['id']}/markdown/skip").status_code == 409


def test_at_the_minimum_one_round_then_a_decision(client):
    fresh = make_item(client, title="Gonna", listed_on="2027-06-20", price="25", min_price="25")
    assert fresh["markdown"]["state"] == "at_minimum"
    assert fresh["markdown"]["steps"] == [] and fresh["markdown"]["next_price_cents"] is None
    assert client.post(f"{API}/vinted/items/{fresh['id']}/markdown/skip").status_code == 409

    old = make_item(client, title="Borsa", listed_on="2027-06-01", price="30", min_price="30")
    assert old["markdown"]["state"] == "review"
    assert AT_MINIMUM in request_text(client, old["id"])["text"]

    # «Lascia così»: no more reminders...
    settled = client.post(f"{API}/vinted/items/{old['id']}/markdown/settle")
    assert settled.status_code == 200 and settled.json()["markdown"]["state"] == "settled"
    assert client.post(f"{API}/vinted/items/{old['id']}/markdown/settle").status_code == 409
    # ...until the price changes (a lower minimum after asking Claude again).
    again = patch(client, old["id"], price="27", min_price="20")["markdown"]
    assert (again["state"], again["since"], again["steps"]) == ("waiting", "2027-06-30", [2400, 2150, 2000])


def test_states_without_markdown(client):
    no_minimum = make_item(client, title="Felpa", listed_on="2027-06-01", price="20")
    assert no_minimum["markdown"]["state"] == "no_minimum"
    unlisted = make_item(client, title="Lampada", price="20", min_price="10")
    assert unlisted["markdown"]["state"] == "inactive"
    sold = make_item(client, title="Libro", listed_on="2027-06-01", price="8", min_price="6")
    sell(client, sold["id"], "8", "2027-06-20")
    assert markdown(client, sold["id"])["state"] == "inactive"
    kept = make_item(client, title="Sciarpa", listed_on="2027-06-01", price="8", min_price="6")
    assert patch(client, kept["id"], is_withdrawn=True)["markdown"]["state"] == "inactive"
    off = make_item(client, title="Quadro", listed_on="2027-06-01", price="80", min_price="60")
    state = patch(client, off["id"], markdown={"plan": "none"})["markdown"]
    assert (state["state"], state["plan"]["text"], state["plan"]["source"]) == ("off", "Niente ribasso", "manual")


# --- the plan of an item ----------------------------------------------------------------------


def test_plan_of_an_item(client):
    item = make_item(client, title="Abito", listed_on="2027-06-25", price="15", min_price="12")
    own = patch(client, item["id"], markdown={"plan": "eur", "amount": "1", "days": 10, "source": "claude"})
    assert own["markdown"]["plan"] == {"kind": "eur", "amount": 100, "days": 10, "source": "claude",
                                       "text": "−1 € ogni 10 giorni"}
    assert own["markdown"]["due_on"] == "2027-07-05"
    assert own["markdown"]["steps"] == [1400, 1300, 1200]
    pct = patch(client, item["id"], markdown={"plan": "pct", "amount": "5", "days": 7})["markdown"]["plan"]
    assert (pct["text"], pct["source"]) == ("−5% ogni 7 giorni", "manual")
    halves = patch(client, item["id"], markdown={"plan": "eur", "amount": "2,50", "days": 7})["markdown"]
    assert halves["plan"]["text"] == "−2,50 € ogni 7 giorni"
    back = patch(client, item["id"], markdown={"plan": "base"})["markdown"]["plan"]
    assert back["source"] == "base"
    # The rest of the item is untouched by a plan.
    assert patch(client, item["id"], markdown={"plan": "base"})["listing"]["price_cents"] == 1500

    for wrong in ({"plan": "pct", "amount": "60", "days": 14}, {"plan": "pct", "amount": "10"},
                  {"plan": "eur", "amount": "0,20", "days": 7}, {"plan": "pct", "amount": "10", "days": 0},
                  {"plan": "pct", "amount": "dieci", "days": 7}, {"plan": "altro"}):
        response = client.patch(f"{API}/vinted/items/{item['id']}", json={"markdown": wrong})
        assert response.status_code == 422, wrong


# --- Claude ----------------------------------------------------------------------------------------


def test_answer_with_a_markdown_line(client):
    response = client.post(f"{API}/vinted/listing/parse", json={"text": "TITOLO: Abito\nDESCRIZIONE:\nBello."
                                                                      "\nPREZZO: 15\nMINIMO: 12\n"
                                                                      "RIBASSO: 1 € ogni 10 giorni\nVERIFICA: niente"})
    answer = response.json()
    assert (answer["min_price_cents"], answer["check"]) == (1200, None)
    assert answer["markdown"] == {"kind": "eur", "amount": 100, "days": 10, "source": "claude",
                                  "text": "−1 € ogni 10 giorni"}
    assert answer["markdown_text"] == "1 € ogni 10 giorni"
    unreadable = parse_answer("TITOLO: A\nPREZZO: 15\nMINIMO: 12\nRIBASSO: dipende dalla stagione")
    assert unreadable["markdown"] is None and unreadable["markdown_text"] == "dipende dalla stagione"


def test_request_of_an_item_on_sale_has_its_prices_and_plan(client):
    item = make_item(client, title="Borsa", listed_on="2027-06-01", price="45", min_price="30")
    patch(client, item["id"], price="40")
    text = request_text(client, item["id"])["text"]
    assert "Prezzi su Vinted: 45,00 € dal 1 giugno, 40,00 € dal 30 giugno\n" in text
    assert "Minimo attuale: 30,00 €\nRibasso attuale: −10% ogni 14 giorni (piano base)\n" in text
    assert "RIBASSO: (quanto e ogni quanti giorni" in text
    assert text.index("MINIMO: (") < text.index("RIBASSO: (") < text.index("VERIFICA: (")


# --- backups ---------------------------------------------------------------------------------------


def test_backup_of_0_18_gets_the_base_plan(client, tmp_path):
    item = make_item(client, title="Giacca", listed_on="2027-06-01", price="35", min_price="25")
    patch(client, item["id"], markdown={"plan": "none"})
    old = tmp_path / "schema10.db"
    old.write_bytes(client.get(f"{API}/backup").content)
    conn = sqlite3.connect(old)
    strip_vinted_markdown(conn)
    conn.execute("PRAGMA user_version = 10")
    conn.commit()
    conn.close()
    response = client.post(f"{API}/restore", content=old.read_bytes(),
                           headers={"Content-Type": "application/octet-stream"})
    assert response.status_code == 200, response.text
    state = markdown(client, item["id"])
    assert (state["plan"]["source"], state["state"]) == ("base", "due")
    live = sqlite3.connect(get_settings().db_path)
    try:
        assert live.execute("PRAGMA user_version").fetchone()[0] == 11
    finally:
        live.close()
