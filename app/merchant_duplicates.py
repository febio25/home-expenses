"""Possible duplicate merchants (0.11.0), offered in Impostazioni → Esercenti
with «Unisci» and «Non sono doppioni».

Two names are offered as a pair when, compared without case, accents,
punctuation and company forms (srl, spa…):

- ``same``: they are the same name ("Lidl" / "LIDL S.r.l.", "Mc Donald's" /
  "McDonalds");
- ``contained``: the words of one appear, in order, inside the other ("Lidl"
  / "Lidl via Roma"), the shorter one being at least 4 letters ("Bar" is
  not matched with "Bar Centrale");
- ``similar``: one letter apart, typed, missing, extra or two swapped
  ("Esselunga" / "Eselunga"), both at least 6 letters long.

Pairs marked as different (merchant_distinct_pairs) are left out. Only the
standard library: a family has a few hundred merchants at most.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from .text import fold

REASONS = {
    "same": "Stesso nome scritto in modo diverso",
    "contained": "Un nome contiene l’altro",
    "similar": "Nomi quasi uguali",
}
REASON_ORDER = {code: index for index, code in enumerate(REASONS)}

MIN_CONTAINED = 4
MIN_SIMILAR = 6

_WORD = re.compile(r"[a-z0-9]+")
# Company forms, on the words of a name: "S.r.l." is ["s", "r", "l"].
_COMPANY_FORMS = [
    ["s", "r", "l", "s"], ["s", "r", "l"], ["srls"], ["srl"],
    ["s", "p", "a"], ["spa"], ["s", "n", "c"], ["snc"], ["s", "a", "s"], ["sas"],
]


@dataclass(frozen=True)
class Key:
    words: tuple[str, ...]
    compact: str


def name_key(name: str) -> Key:
    """The words of a name without case, accents, punctuation and company
    forms, and the same words joined."""
    words = _WORD.findall(fold(name) or "")
    stripped = list(words)
    for form in _COMPANY_FORMS:
        size = len(form)
        index = 0
        while index + size <= len(stripped):
            if stripped[index:index + size] == form and len(stripped) > size:
                del stripped[index:index + size]
            else:
                index += 1
    return Key(tuple(stripped), "".join(stripped))


def _contains(longer: tuple[str, ...], shorter: tuple[str, ...]) -> bool:
    size = len(shorter)
    return any(longer[index:index + size] == shorter for index in range(len(longer) - size + 1))


def one_edit_apart(a: str, b: str) -> bool:
    """True when ``b`` is ``a`` with one letter changed, added, removed or
    two neighbouring letters swapped. Equal strings are not."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    start = 0
    while start < len(a) and a[start] == b[start]:
        start += 1
    if len(a) == len(b):
        rest_a, rest_b = a[start + 1:], b[start + 1:]
        if rest_a == rest_b:
            return True  # one letter changed
        # Two neighbouring letters swapped: "lnu" / "nlu".
        return (
            start + 1 < len(a)
            and a[start] == b[start + 1]
            and a[start + 1] == b[start]
            and a[start + 2:] == b[start + 2:]
        )
    return a[start:] == b[start + 1:]  # one letter added in b


def reason_for(a: Key, b: Key) -> str | None:
    if not a.compact or not b.compact:
        return None
    if a.compact == b.compact:
        return "same"
    short, long_ = (a, b) if len(a.words) <= len(b.words) else (b, a)
    if len(short.words) < len(long_.words) and len(short.compact) >= MIN_CONTAINED:
        if _contains(long_.words, short.words):
            return "contained"
    if min(len(a.compact), len(b.compact)) >= MIN_SIMILAR and one_edit_apart(a.compact, b.compact):
        return "similar"
    return None


def find_pairs(merchants: list[dict], distinct: set[tuple[int, int]]) -> list[dict]:
    """``merchants``: dicts with at least ``id``, ``name`` and
    ``expense_count``. ``distinct``: pairs (smaller id, larger id) marked as
    different. Returns ``{reason, reason_name, merchants: [first, second]}``,
    the most likely duplicates first; in each pair the merchant with more
    expenses comes first (usually the name to keep)."""
    keys = {merchant["id"]: name_key(merchant["name"]) for merchant in merchants}
    pairs = []
    ordered = sorted(merchants, key=lambda merchant: merchant["id"])
    for index, first in enumerate(ordered):
        for second in ordered[index + 1:]:
            if (first["id"], second["id"]) in distinct:
                continue
            reason = reason_for(keys[first["id"]], keys[second["id"]])
            if reason is None:
                continue
            pair = sorted(
                (first, second), key=lambda merchant: (-merchant["expense_count"], merchant["id"])
            )
            pairs.append({"reason": reason, "reason_name": REASONS[reason], "merchants": pair})
    pairs.sort(key=lambda pair: (
        REASON_ORDER[pair["reason"]],
        -sum(merchant["expense_count"] for merchant in pair["merchants"]),
        fold(pair["merchants"][0]["name"]),
    ))
    return pairs


def distinct_pairs(db: sqlite3.Connection) -> set[tuple[int, int]]:
    rows = db.execute("SELECT merchant_a_id, merchant_b_id FROM merchant_distinct_pairs").fetchall()
    return {(row[0], row[1]) for row in rows}


__all__ = ["REASONS", "name_key", "one_edit_apart", "reason_for", "find_pairs", "distinct_pairs"]
