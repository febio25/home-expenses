"""Vinted listings written with Claude (0.10.0), by hand: the app builds the
request (the item's data, the rules and a fixed answer format), the user
gives it to the Claude app, then pastes the answer back. Nothing here
calls anything outside the app.

0.11.0: the rules follow the style of Nastia's own ads (a natural title,
a few sentences of prose, an example of hers) and include the price rules,
so the request is enough on its own. The same rules, in more detail, are in
the skill «annunci-vinted» that the README asks to add to the Claude
account. The answer format must stay the same in both: if one changes,
change the other, or the answer is no longer recognised.
"""

from __future__ import annotations

import re
from datetime import date

from .money import AmountError, format_cents, parse_amount
from .vinted_schemas import (
    VINTED_ANY_KIND_FIELDS,
    VINTED_CONDITIONS,
    VINTED_DETAIL_LABELS,
    VINTED_KIND_FIELDS,
    VINTED_KINDS,
)

MONTHS = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]

# Labels of the request: "Colore/materiale" as in the Project's instructions.
REQUEST_LABELS = {**VINTED_DETAIL_LABELS, "color_material": "Colore/materiale"}

INTRO = "Scrivi titolo e descrizione per un annuncio Vinted (Italia) di questo articolo e proponi il prezzo."
STYLE = """Come scrivere
- Titolo: una frase breve e naturale, come la scriverebbe una persona: cos'è, marca, il dettaglio più utile, colore e taglia. Per i libri «Titolo - Autore». Niente hashtag, elenchi di parole chiave, emoji o simboli.
- Descrizione: in prosa, da 1 a 4 frasi, tono cordiale e sincero. Prima cos'è e com'è fatto (materiale, colore, dettagli, misure dentro la frase), poi le condizioni, con i difetti detti chiaramente e il rimando alle foto. Niente elenchi puntati, hashtag, emoji, parole tutte in maiuscolo o frasi pubblicitarie («affare», «spedizione veloce»).
- Non inventare dettagli che non sono nei dati o nella foto (marca, materiale, misure, difetti, autenticità): se manca qualcosa d'importante, scrivilo in VERIFICA.
- Prezzo: realistico per Vinted, tenendo conto di stato, marca e prezzi simili se ci sono; in euro interi, un po' sopra il prezzo a cui mi aspetto di vendere, per lasciare spazio alle offerte. Senza prezzi simili, una stima prudente, e in VERIFICA il consiglio di confrontarla con annunci simili.
- Minimo: il prezzo sotto cui non conviene scendere; di norma non sotto quanto l'ho pagato."""
ON_SALE = "L'articolo è già in vendita: proponi un PREZZO aggiornato e spiega in VERIFICA perché."
# One of Nastia's own ads on Vinted, barely shortened: Claude copies the tone.
EXAMPLE = """Esempio dello stile (solo per il tono, non per i contenuti):
TITOLO: Giubbotto piumino Benetton taglia 44 (M) trapuntato collo alto
DESCRIZIONE:
Giubbotto piumino da donna di Benetton usato ma in ottime condizioni, con piccolissimi difetti che faccio vedere nelle ultime due foto.
È davvero caldo e comodo, in piuma d'oca, con collo alto, zip asimmetrica laterale e fiocco decorativo in vita."""
ANSWER_FORMAT = """Rispondi solo in questo formato:
TITOLO: …
DESCRIZIONE:
…
PREZZO: (solo il numero, in euro)
MINIMO: (prezzo sotto cui non scendere)
VERIFICA: (cose da controllare prima di pubblicare, oppure «niente»)"""


def italian_date(value: str | date) -> str:
    """"3 novembre 2026"."""
    day = date.fromisoformat(value) if isinstance(value, str) else value
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def euro(cents: int) -> str:
    """"1250,00 €": the amount as an Italian reads it (no thousands dot)."""
    return f"{format_cents(cents, ',')} €"


def detail_fields(kind: str | None) -> list[str]:
    """The details that make sense for a kind of item, in request order."""
    return VINTED_KIND_FIELDS.get(kind or "", VINTED_ANY_KIND_FIELDS)


def build_request(item: dict, today: date) -> str:
    """The message for Claude about one item (as returned by item_out).
    Lines without a value are left out."""
    details = item["details"]
    has_photo = item["photo"] is not None
    lines = [
        INTRO + (" La foto è allegata." if has_photo else " Non ho una foto: basati solo sui dati."),
        "",
    ]

    def add(label: str, value: str | None) -> None:
        if value:
            lines.append(f"{label}: {value}")

    add("Tipo", details["kind_name"])
    add("Articolo", item["title"])
    for field in detail_fields(details["kind"]):
        value = details["condition_name"] if field == "condition" else details[field]
        add(REQUEST_LABELS[field], value)
    purchase = item["purchase"]
    if purchase:
        bought = f"{euro(purchase['amount_cents'])} il {italian_date(purchase['expense_date'])}"
        if purchase["merchant_name"]:
            bought += f", da {purchase['merchant_name']}"
        add("Comprato a", bought)
    add("Prezzi simili visti su Vinted", details["similar_prices"])
    add("Note", item["note"])
    listing = item["listing"]
    on_sale = item["status"] == "listed" and item["listed_on"] is not None
    if on_sale:
        days = max(0, (today - date.fromisoformat(str(item["listed_on"]))).days)
        since = "da oggi" if days == 0 else "da 1 giorno" if days == 1 else f"da {days} giorni"
        price = f" a {euro(listing['price_cents'])}" if listing["price_cents"] else ""
        add("In vendita", f"{since}{price}, non ancora venduto")
        # The title on Vinted: the ad's own, or the item's name when the ad
        # has a text but no title of its own (0.11.0).
        add("Titolo attuale", listing["title"] or (item["title"] if listing["description"] else None))
    lines += ["", STYLE]
    if on_sale:
        lines.append(ON_SALE)
    lines += ["", EXAMPLE, "", ANSWER_FORMAT]
    return "\n".join(lines)


def is_request(text: str) -> bool:
    """True for the request itself (of this version or of 0.10.0), pasted
    where Claude's answer was expected."""
    return "Rispondi solo in questo formato" in text and (
        INTRO in text or "Aiutami a preparare un annuncio Vinted" in text
    )


# --- reading the answer -----------------------------------------------------------

# A label at the start of a line, in any case, maybe in bold or as a heading
# ("**TITOLO:**", "## Prezzo:", "- Minimo :"), and what follows on its line.
_LABEL = re.compile(
    r"^[\s>*_#\-•]*(TITOLO|DESCRIZIONE|PREZZO|MINIMO|VERIFICA)[\s*_]*:[\s*_]*(.*)$",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d[\d.,]*")
_NOTHING = {"niente", "nulla", "nessuna", "nessuno", "-", "—", "no"}


def _clean_block(lines: list[str]) -> str:
    text = "\n".join(line.rstrip() for line in lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Bold markers left around a value ("**Giacca**"), quotes around a title.
    text = re.sub(r"^\*\*(.*)\*\*$", r"\1", text, flags=re.DOTALL).strip()
    return text


def _price(text: str | None) -> int | None:
    """The first amount in a line such as "25", "25 €", "€ 22,50", "circa 30 euro"."""
    if not text:
        return None
    match = _NUMBER.search(text)
    if not match:
        return None
    token = match.group(0).rstrip(".,")
    try:
        return parse_amount(token)
    except AmountError:
        return None


def parse_answer(text: str) -> dict:
    """Split Claude's answer into title, description, prices and the things
    to check. Never an error: an answer not in the format becomes the
    description, without prices."""
    blocks: dict[str, list[str]] = {}
    current = None
    for line in text.replace("\r\n", "\n").split("\n"):
        match = _LABEL.match(line)
        if match:
            current = match.group(1).upper()
            blocks.setdefault(current, [])
            if match.group(2).strip():
                blocks[current].append(match.group(2))
        elif current is not None:
            blocks[current].append(line)
    if "TITOLO" not in blocks and "DESCRIZIONE" not in blocks:
        whole = text.strip()
        return {
            "recognized": False,
            "title": None,
            "description": whole or None,
            "price_cents": None,
            "min_price_cents": None,
            "check": None,
        }
    title = " ".join(_clean_block(blocks.get("TITOLO", [])).split()).strip("«»\"' ") or None
    description = _clean_block(blocks.get("DESCRIZIONE", [])) or None
    price = _price(_clean_block(blocks.get("PREZZO", [])))
    minimum = _price(_clean_block(blocks.get("MINIMO", [])))
    if minimum is not None and price is not None and minimum > price:
        minimum = None
    check = _clean_block(blocks.get("VERIFICA", [])) or None
    if check and check.strip(" .!«»\"").lower() in _NOTHING:
        check = None
    return {
        "recognized": True,
        "title": title,
        "description": description,
        "price_cents": price,
        "min_price_cents": minimum,
        "check": check,
    }


def options() -> dict:
    return {
        "kinds": [
            {"code": code, "name": name, "fields": VINTED_KIND_FIELDS[code]}
            for code, name in VINTED_KINDS.items()
        ],
        "conditions": [{"code": code, "name": name} for code, name in VINTED_CONDITIONS.items()],
        "fields": [{"field": field, "name": name} for field, name in VINTED_DETAIL_LABELS.items()],
    }


__all__ = ["build_request", "parse_answer", "is_request", "options", "detail_fields", "italian_date", "euro"]
