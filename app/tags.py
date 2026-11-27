"""Tags in the notes of the expenses (0.18.0, F2): a word that starts with
"#" in the note ("Cena #vacanze-2026") groups expenses of different
categories under one purpose: a trip, a job in the house. No column of
their own: the note is the only place they live, so they travel with the
CSV and need no migration.

A tag is "#" followed by a letter or a digit, then letters, digits, "-" or
"_". Two tags are the same when they are equal without case and accents
(``fold``): "#Vacanze" and "#vacanze" are one tag.

``has_tag`` is registered as an SQL function on every connection (see
db.connect), so the filter of the list runs in the query.
"""

from __future__ import annotations

import re

from .text import fold

# Not after a letter, digit or "&": "AT&T#1" or "a#b" are not tags.
TAG_RE = re.compile(r"(?<![\w&])#([^\W_][\w-]*)")
MAX_TAG_LENGTH = 40


def tags_in(note: str | None) -> list[str]:
    """The tags of a note, without "#", as written, each once, in order.
    Trailing "-" or "_" are left out: "#casa-" is "casa"."""
    if not note:
        return []
    seen: set[str] = set()
    found = []
    for match in TAG_RE.finditer(note):
        tag = match.group(1).rstrip("-_")[:MAX_TAG_LENGTH]
        key = fold(tag)
        if tag and key not in seen:
            seen.add(key)
            found.append(tag)
    return found


def clean_tag(text: str | None) -> str | None:
    """A tag asked for by the filter ("#vacanze" or "vacanze"), folded, or
    None when it is not a tag at all."""
    if text is None:
        return None
    tags = tags_in("#" + text.strip().removeprefix("#"))
    return fold(tags[0]) if tags else None


def has_tag(note: str | None, folded_tag: str | None) -> int:
    """1 when the note carries the tag (already folded), else 0."""
    if not note or not folded_tag or "#" not in note:
        return 0
    return int(any(fold(tag) == folded_tag for tag in tags_in(note)))
