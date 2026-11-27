"""Tags of the expenses (0.18.0, F2): the "#words" already used in the
notes, for the suggestions while typing a note and for the «Etichetta»
filter of the search. Read from the notes each time: they have no table."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..schemas import TagOut
from ..security import current_user
from ..tags import tags_in
from ..text import fold

router = APIRouter(prefix="/tags", tags=["tags"], dependencies=[Depends(current_user)])


@router.get("", response_model=list[TagOut])
def list_tags(db: sqlite3.Connection = Depends(get_db)):
    """Every tag of the expense notes, most recently used first. Two
    spellings of one tag ("#Vacanze", "#vacanze") are one entry, written as
    in its latest expense; ``total_cents`` sums the expenses carrying it."""
    rows = db.execute(
        "SELECT note, expense_date, amount_cents FROM expenses"
        " WHERE instr(note, '#') > 0 ORDER BY expense_date DESC, id DESC"
    ).fetchall()
    found: dict[str, dict] = {}
    for row in rows:
        for tag in tags_in(row["note"]):
            entry = found.setdefault(
                fold(tag), {"tag": tag, "count": 0, "total_cents": 0, "last_date": row["expense_date"]}
            )
            entry["count"] += 1
            entry["total_cents"] += row["amount_cents"]
    return list(found.values())
