"""Text search over expenses and incomes (0.9.0): what the search box of
"Movimenti" types is compared without case and without accents, so
"caffe" finds "Caffè" and "esselunga" finds "ESSELUNGA".

``fold`` is also registered as an SQL function on every connection (see
db.connect), so the comparison happens in the query.
"""

from __future__ import annotations

import unicodedata

from .money import AmountError, parse_amount

# The longest text the search accepts: a merchant name or a few words.
MAX_QUERY_LENGTH = 80


def fold(text: str | None) -> str | None:
    """Lower case, accents removed: "Caffè Né" -> "caffe ne"."""
    if text is None:
        return None
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def clean_query(text: str | None) -> str | None:
    """The searched text with spaces tidied, or None when there is none."""
    if text is None:
        return None
    return " ".join(text.split()) or None


def query_cents(text: str) -> int | None:
    """The text read as an amount ("12,50", "12.5", "12 €"), else None: an
    amount search finds the movements of exactly that amount."""
    try:
        return parse_amount(text)
    except AmountError:
        return None


def search_clause(text: str, columns: list[str], amount_column: str) -> tuple[str, list]:
    """SQL condition (in parentheses) and parameters: the folded text inside
    any of ``columns``, or an amount equal to the text read as an amount.

    ``instr`` and not LIKE, so "%" and "_" typed in the box are plain text.
    """
    folded = fold(text)
    parts = [f"instr(fold({column}), ?) > 0" for column in columns]
    params: list = [folded] * len(columns)
    cents = query_cents(text)
    if cents is not None:
        parts.append(f"{amount_column} = ?")
        params.append(cents)
    return f"({' OR '.join(parts)})", params
