"""Vinted listings written with Claude (0.10.0): details of an item, the
request to share, reading the answer back, the asking price and its history."""

from __future__ import annotations

import csv
import io

from app.vinted_listing import EXAMPLE, STYLE, parse_answer
from tests.conftest import PINNED_TODAY
from tests.test_vinted import API, JPEG, THUMB, b64, bought, make_item, sell

TODAY = PINNED_TODAY.isoformat()
ANSWER_FORMAT = """Rispondi solo in questo formato:
TITOLO: …
DESCRIZIONE:
…
PREZZO: (solo il numero, in euro)
MINIMO: (prezzo sotto cui non scendere)
RIBASSO: (quanto e ogni quanti giorni, per esempio «10% ogni 14 giorni» o «2 € ogni 7 giorni»; oppure «niente»)
VERIFICA: (cose da controllare prima di pubblicare, oppure «niente»)"""


def patch(client, item_id, **body):
    response = client.patch(f"{API}/vinted/items/{item_id}", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def request_text(client, item_id):
    response = client.get(f"{API}/vinted/items/{item_id}/listing-request")
    assert response.status_code == 200, response.text
    return response.json()


def history(item):
    return [(change["price_cents"], change["changed_on"]) for change in item["listing"]["price_changes"]]


# --- details ---------------------------------------------------------------------------


def test_options(client):
    options = client.get(f"{API}/vinted/listing/options").json()
    assert [k["code"] for k in options["kinds"]] == ["clothing", "bag", "book", "other"]
    assert options["kinds"][0] == {
        "code": "clothing", "name": "Abbigliamento",
        "fields": ["brand", "size", "condition", "color_material", "measurements", "defects"],
    }
    assert options["kinds"][2]["fields"] == ["book_author", "book_publisher_year", "condition", "defects"]
    assert [c["name"] for c in options["conditions"]] == [
        "Nuovo con cartellino", "Nuovo senza cartellino", "Ottime condizioni", "Buone condizioni",
        "Discrete condizioni"]
    assert {"field": "color_material", "name": "Colore e materiale"} in options["fields"]


def test_details_on_create_and_patch(client):
    item = make_item(client, title="Giacca in jeans", kind="clothing", brand="  Levi's ", size="M",
                     condition="very_good", color_material="blu,   cotone")
    details = item["details"]
    assert (details["kind"], details["kind_name"]) == ("clothing", "Abbigliamento")
    assert (details["brand"], details["size"], details["color_material"]) == ("Levi's", "M", "blu, cotone")
    assert (details["condition"], details["condition_name"]) == ("very_good", "Ottime condizioni")
    assert details["defects"] is None and details["similar_prices"] is None
    assert item["listing"] == {
        "title": None, "effective_title": "Giacca in jeans", "description": None, "price_cents": None,
        "min_price_cents": None, "start_price_cents": None, "price_changes": []}

    changed = patch(client, item["id"], defects="segno sul polsino", similar_prices="20, 25, 18", brand=None)
    assert changed["details"]["brand"] is None  # null clears
    assert changed["details"]["size"] == "M"     # not sent: untouched
    assert changed["details"]["defects"] == "segno sul polsino"
    assert patch(client, item["id"], size="   ")["details"]["size"] is None  # blank clears too

    for body in ({"kind": "shoes"}, {"condition": "perfect"}, {"brand": "x" * 61}, {"listing_title": "x" * 201}):
        response = client.patch(f"{API}/vinted/items/{item['id']}", json=body)
        assert response.status_code == 422, body


def test_listing_text_and_prices(client):
    item = make_item(client, purchase=bought("12", "2026-11-02"))
    saved = patch(client, item["id"], listing_title="  Borsa   a tracolla in pelle ",
                  listing_description="Borsa marrone.  \r\n\r\n\r\n\r\nTracolla regolabile.\n", price="25",
                  min_price="15,50")
    listing = saved["listing"]
    assert listing["title"] == "Borsa a tracolla in pelle"
    assert listing["description"] == "Borsa marrone.\n\nTracolla regolabile."
    assert (listing["price_cents"], listing["min_price_cents"]) == (2500, 1550)
    assert listing["price_changes"] == []  # not on Vinted yet: no history

    bad = client.patch(f"{API}/vinted/items/{item['id']}", json={"min_price": "30"})
    assert bad.status_code == 422
    assert bad.json()["detail"] == "Il prezzo minimo non può superare il prezzo dell'annuncio."
    assert client.patch(f"{API}/vinted/items/{item['id']}", json={"price": "abc"}).status_code == 422
    cleared = patch(client, item["id"], min_price="", price=None)
    assert (cleared["listing"]["price_cents"], cleared["listing"]["min_price_cents"]) == (None, None)


# --- price history -----------------------------------------------------------------------


def test_price_history_follows_publication_and_changes(client):
    item = make_item(client, title="Stivali", price="25", min_price="15")
    published = patch(client, item["id"], listed_on="2026-11-01")
    assert history(published) == [(2500, "2026-11-01")]
    assert published["listing"]["start_price_cents"] == 2500

    lower = patch(client, item["id"], price="22,50")
    assert history(lower) == [(2500, "2026-11-01"), (2250, TODAY)]
    corrected = patch(client, item["id"], price="20")  # same day: corrects that day's price
    assert history(corrected) == [(2500, "2026-11-01"), (2000, TODAY)]
    assert history(patch(client, item["id"], price="20")) == history(corrected)  # same price: nothing
    assert history(patch(client, item["id"], note="tacco basso")) == history(corrected)

    moved = patch(client, item["id"], listed_on="2026-11-03")  # the day of publication follows
    assert history(moved) == [(2500, "2026-11-03"), (2000, TODAY)]
    assert moved["listing"]["start_price_cents"] == 2500 and moved["listing"]["price_cents"] == 2000

    back = patch(client, item["id"], listed_on=None)  # never on Vinted after all
    assert history(back) == []
    again = patch(client, item["id"], listed_on="2026-11-10")
    assert history(again) == [(2000, "2026-11-10")]


def test_price_history_with_publication_and_price_together(client):
    item = make_item(client, title="Felpa", listed_on="2026-11-05", price="18")
    assert history(item) == [(1800, "2026-11-05")]  # created already on Vinted
    no_price = make_item(client, title="Libro", listed_on="2026-11-05")
    assert history(no_price) == []
    priced = patch(client, no_price["id"], price="9")  # first price set later: from today
    assert history(priced) == [(900, TODAY)]

    other = make_item(client, title="Zaino", price="30")
    both = patch(client, other["id"], listed_on="2026-11-06", price="28")
    assert history(both) == [(2800, "2026-11-06")]

    # Published today, lowered today: the price of the publication stays.
    same_day = make_item(client, title="Borsa", price="25")
    patch(client, same_day["id"], listed_on=TODAY)
    assert history(patch(client, same_day["id"], price="22,50")) == [(2500, TODAY), (2250, TODAY)]
    assert history(patch(client, same_day["id"], price="21")) == [(2500, TODAY), (2100, TODAY)]


def test_no_price_history_once_sold_or_withdrawn(client):
    item = make_item(client, title="Gonna", listed_on="2026-11-02", price="12")
    sell(client, item["id"], "11", "2026-11-20")
    assert history(patch(client, item["id"], price="10")) == [(1200, "2026-11-02")]

    kept = make_item(client, title="Sciarpa", listed_on="2026-11-02", price="8")
    patch(client, kept["id"], is_withdrawn=True)
    assert history(patch(client, kept["id"], price="6")) == [(800, "2026-11-02")]


# --- request for Claude -------------------------------------------------------------------


def test_request_for_clothing_with_everything(client):
    item = make_item(client, title="Giacca in jeans", note="indossata due volte",
                     purchase=bought("12", "2026-11-03", merchant="Mercatino Usato"),
                     kind="clothing", brand="Levi's", size="M", condition="very_good",
                     color_material="blu, cotone", measurements="spalle 45 cm, lunghezza 62 cm",
                     defects="piccolo segno sul polsino sinistro", similar_prices="20, 25, 18, 30",
                     book_author="non va nel messaggio")
    client.put(f"{API}/vinted/items/{item['id']}/photo", json={"image": b64(JPEG), "thumb": b64(THUMB)})
    answer = request_text(client, item["id"])
    assert answer["has_photo"] is True
    assert answer["text"] == f"""Scrivi titolo e descrizione per un annuncio Vinted (Italia) di questo articolo e proponi il prezzo. La foto è allegata.

Tipo: Abbigliamento
Articolo: Giacca in jeans
Marca: Levi's
Taglia: M
Stato: Ottime condizioni
Colore/materiale: blu, cotone
Misure: spalle 45 cm, lunghezza 62 cm
Difetti: piccolo segno sul polsino sinistro
Comprato a: 12,00 € il 3 novembre 2026, da Mercatino Usato
Prezzi simili visti su Vinted: 20, 25, 18, 30
Note: indossata due volte

{STYLE}

{EXAMPLE}

{ANSWER_FORMAT}"""
    # 0.11.0: the rules follow Nastia's ads, with the price rules inside.
    for rule in ("una frase breve e naturale", "Niente hashtag", "in prosa, da 1 a 4 frasi",
                 "di norma non sotto quanto l'ho pagato", "in euro interi"):
        assert rule in answer["text"], rule


def test_request_for_a_book_and_for_an_item_without_details(client):
    book = make_item(client, title="Il nome della rosa", kind="book", book_author="Umberto Eco",
                     book_publisher_year="Bompiani, 1980", condition="good", brand="ignorata")
    text = request_text(client, book["id"])["text"]
    assert "Non ho una foto: basati solo sui dati." in text.splitlines()[0]
    assert "Tipo: Libro\nArticolo: Il nome della rosa\nAutore: Umberto Eco\nEditore e anno: Bompiani, 1980\n" \
        "Stato: Buone condizioni\n\nCome scrivere\n" in text
    assert "Marca" not in text and "Comprato a" not in text

    bare = make_item(client, title="Lampada")
    lines = request_text(client, bare["id"])["text"].splitlines()
    assert lines[2:4] == ["Articolo: Lampada", ""]


def test_request_for_an_item_already_on_sale(client):
    item = make_item(client, title="Borsa", listed_on="2027-06-18", price="25", listing_title="Borsa pelle")
    text = request_text(client, item["id"])["text"]
    assert "In vendita: da 12 giorni a 25,00 €, non ancora venduto\nTitolo attuale: Borsa pelle\n" in text
    # 0.19.0: without a minimum, no "Minimo attuale"; the plan is the base.
    assert "Ribasso attuale: −10% ogni 14 giorni (piano base)\n" in text and "Minimo attuale" not in text
    assert "L'articolo è già in vendita: proponi un PREZZO aggiornato e spiega in VERIFICA perché." in text
    assert text.endswith(ANSWER_FORMAT)
    assert client.get(f"{API}/vinted/items/999/listing-request").status_code == 404


# --- reading the answer ---------------------------------------------------------------------


def parse(client, text):
    response = client.post(f"{API}/vinted/listing/parse", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_parse_an_answer_in_format(client):
    answer = parse(client, """TITOLO: Giacca jeans Levi's taglia M
DESCRIZIONE:
Giacca in jeans Levi's, taglia M, blu.
Ottime condizioni, piccolo segno sul polsino sinistro (vedi foto).

Misure: spalle 45 cm, lunghezza 62 cm.
PREZZO: 25
MINIMO: 18
VERIFICA: niente""")
    assert answer == {
        "recognized": True,
        "title": "Giacca jeans Levi's taglia M",
        "description": "Giacca in jeans Levi's, taglia M, blu.\nOttime condizioni, piccolo segno sul polsino"
                       " sinistro (vedi foto).\n\nMisure: spalle 45 cm, lunghezza 62 cm.",
        "price_cents": 2500,
        "min_price_cents": 1800,
        "check": None,
        "markdown": None,  # 0.19.0: no line RIBASSO, the item keeps its plan
        "markdown_text": None,
    }
    # Nothing saved by reading.
    assert client.get(f"{API}/vinted/items").json() == []


def test_parse_tolerates_markdown_case_and_prices_in_words():
    answer = parse_answer("""Ecco l'annuncio:

**TITOLO:** «Borsa a tracolla marrone»
**Descrizione:**
Borsa in similpelle.
## Prezzo: € 22,50
- minimo : circa 15 euro
**VERIFICA:**
Controlla le misure.
Guarda se ci sono graffi.
""")
    assert answer["recognized"] is True
    assert answer["title"] == "Borsa a tracolla marrone"
    assert answer["description"] == "Borsa in similpelle."
    assert (answer["price_cents"], answer["min_price_cents"]) == (2250, 1500)
    assert answer["check"] == "Controlla le misure.\nGuarda se ci sono graffi."


def test_parse_odd_prices_and_answers_out_of_format():
    odd = parse_answer("TITOLO: Felpa\nDESCRIZIONE: Felpa grigia.\nPREZZO: da decidere\nMINIMO: 30\nVERIFICA: Niente.")
    assert (odd["title"], odd["description"]) == ("Felpa", "Felpa grigia.")
    assert (odd["price_cents"], odd["min_price_cents"], odd["check"]) == (None, 3000, None)
    higher = parse_answer("TITOLO: Felpa\nPREZZO: 20 €\nMINIMO: 25 €")
    assert (higher["price_cents"], higher["min_price_cents"]) == (2000, None)  # minimum above price: dropped
    assert higher["description"] is None

    loose = parse_answer("Ti suggerisco di chiamarla Felpa grigia e di chiedere 20 euro.")
    assert loose == {
        "recognized": False, "title": None,
        "description": "Ti suggerisco di chiamarla Felpa grigia e di chiedere 20 euro.",
        "price_cents": None, "min_price_cents": None, "check": None,
        "markdown": None, "markdown_text": None}
    assert parse_answer("   ")["description"] is None


def test_parse_validation_and_access(client, anon):
    assert client.post(f"{API}/vinted/listing/parse", json={"text": "x" * 20001}).status_code == 422
    assert anon.post(f"{API}/vinted/listing/parse", json={"text": "TITOLO: x"}).status_code in (401, 403)
    assert anon.get(f"{API}/vinted/listing/options").status_code == 401


# --- CSV, backup -------------------------------------------------------------------------------


def test_csv_columns_of_the_listing(client):
    item = make_item(client, title="Stivali", kind="clothing", brand="Clarks", size="38", condition="good",
                     price="40", min_price="25", listed_on="2026-11-01")
    patch(client, item["id"], price="35")
    make_item(client, title="Libro", kind="book")
    rows = list(csv.DictReader(io.StringIO(client.get(f"{API}/export/vinted.csv").content.decode("utf-8"))))
    by_title = {row["articolo"]: row for row in rows}
    stivali = by_title["Stivali"]
    assert [stivali[c] for c in ("tipo", "marca", "taglia", "condizioni", "prezzo_partenza", "prezzo_attuale",
                                 "prezzo_minimo", "cambi_prezzo")] == [
        "Abbigliamento", "Clarks", "38", "Buone condizioni", "40.00", "35.00", "25.00", "1"]
    libro = by_title["Libro"]
    assert [libro[c] for c in ("tipo", "prezzo_partenza", "prezzo_attuale", "cambi_prezzo")] == ["Libro", "", "", ""]
    excel = client.get(f"{API}/export/vinted.csv?format=excel_it").content.decode("utf-8-sig")
    assert ";Abbigliamento;Clarks;38;Buone condizioni;40,00;35,00;25,00;1" in excel


def test_backup_and_restore_keep_the_listing_and_its_history(client):
    item = make_item(client, title="Felpa", listed_on="2026-11-05", price="18", listing_title="Felpa grigia")
    patch(client, item["id"], price="15")
    backup = client.get(f"{API}/backup").content
    client.delete(f"{API}/vinted/items/{item['id']}")
    assert client.post(f"{API}/restore", content=backup).status_code == 200
    restored = client.get(f"{API}/vinted/items/{item['id']}").json()
    assert restored["listing"]["title"] == "Felpa grigia"
    assert history(restored) == [(1800, "2026-11-05"), (1500, TODAY)]


def test_deleting_the_item_deletes_its_price_history(client, app):
    from app.config import get_settings
    import sqlite3

    item = make_item(client, title="Felpa", listed_on="2026-11-05", price="18")
    assert client.delete(f"{API}/vinted/items/{item['id']}").status_code == 204
    conn = sqlite3.connect(get_settings().db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM vinted_price_changes").fetchone()[0] == 0
    finally:
        conn.close()


# --- 0.11.0 ------------------------------------------------------------------------------


def test_title_of_the_ad_defaults_to_the_item_name(client):
    item = make_item(client, title="Giacca jeans")
    assert (item["listing"]["title"], item["listing"]["effective_title"]) == (None, "Giacca jeans")
    own = patch(client, item["id"], listing_title="Giacca jeans Levi's blu taglia M")
    assert own["listing"]["effective_title"] == "Giacca jeans Levi's blu taglia M"
    back = patch(client, item["id"], listing_title=None)
    assert (back["listing"]["title"], back["listing"]["effective_title"]) == (None, "Giacca jeans")
    # Renamed in the app: the ad without a title of its own follows.
    assert patch(client, item["id"], title="Giacca")["listing"]["effective_title"] == "Giacca"


def test_request_of_an_item_on_sale_names_the_title_in_use(client):
    item = make_item(client, title="Borsa", listed_on="2027-06-18", price="25",
                     listing_description="Borsa in pelle marrone.")
    assert "Titolo attuale: Borsa\n" in request_text(client, item["id"])["text"]
    bare = make_item(client, title="Felpa", listed_on="2027-06-18")
    assert "Titolo attuale" not in request_text(client, bare["id"])["text"]  # no ad written yet


def test_the_request_pasted_instead_of_the_answer_is_refused(client):
    item = make_item(client, title="Giacca jeans", kind="clothing")
    text = request_text(client, item["id"])["text"]
    for pasted in (text, f"  {text}\n", text.replace(
            "Scrivi titolo e descrizione per un annuncio Vinted (Italia) di questo articolo e proponi il prezzo.",
            "Aiutami a preparare un annuncio Vinted (Italia) per questo articolo.")):
        response = client.post(f"{API}/vinted/listing/parse", json={"text": pasted})
        assert response.status_code == 422
        assert response.json()["detail"].startswith("Questa è la richiesta per Claude")
    # An answer that only mentions the format is still read.
    answer = parse(client, "TITOLO: Giacca\nDESCRIZIONE:\nBella.\nVERIFICA: Rispondi solo in questo formato?")
    assert answer["title"] == "Giacca"


def test_new_purchase_has_no_merchant_unless_given(client):
    plain = make_item(client, purchase=bought())
    assert plain["purchase"]["merchant_name"] is None
    assert "Comprato a: 12,00 € il 2 novembre 2026\n" in request_text(client, plain["id"])["text"]
    vinted = make_item(client, purchase=bought(merchant="Vinted"))
    assert vinted["purchase"]["merchant_name"] == "Vinted"
