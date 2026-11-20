"""Amount parsing and formatting.

Amounts are stored as integer cents and never touch floating point.
"""

from __future__ import annotations

import re

MAX_CENTS = 100_000_000  # 1,000,000.00 EUR: anything above is a typo

# Lenient on purpose: "12," and ",50" are what a thumb types in a hurry.
_PLAIN = re.compile(r"^(\d*)(?:[.,](\d{0,2}))?$")
_GROUPED = re.compile(r"^(\d{1,3}(?:[.,]\d{3})+)[.,](\d{1,2})$")
# "1.850": Italian thousands, or decimals the English way? Still refused,
# with a message that says how to write it (salaries are typed like this).
_DOT_THOUSANDS = re.compile(r"^\d{1,3}(?:\.\d{3})+$")


class AmountError(ValueError):
    """Raised with an Italian, user-facing message."""


def parse_amount(text: str) -> int:
    """Convert user input such as "12,50", "12.5" or "1.234,56" to cents.

    Accepted: comma or dot as decimal separator, at most two decimals, an
    optional euro sign and spaces. A thousands separator is accepted only
    when a decimal part follows it, because "1.234" alone is ambiguous.
    """
    if not isinstance(text, str):
        raise AmountError("Importo non valido.")
    cleaned = text.replace("€", "").replace(" ", "").replace(" ", "").strip()
    if not cleaned:
        raise AmountError("Inserisci un importo.")
    if cleaned.startswith("-"):
        raise AmountError("L'importo deve essere positivo.")

    match = _PLAIN.match(cleaned)
    if match and re.search(r"\d", cleaned):
        whole, decimals = match.group(1) or "0", match.group(2) or ""
    else:
        grouped = _GROUPED.match(cleaned)
        if not grouped:
            if _DOT_THOUSANDS.match(cleaned):
                digits = cleaned.replace(".", "")
                raise AmountError(f"Importo ambiguo: scrivi {digits} oppure {cleaned},00.")
            if re.match(r"^\d+[.,]\d{3,}$", cleaned):
                raise AmountError("Usa al massimo due decimali (es. 12,50).")
            raise AmountError("Importo non valido: usa un formato come 12,50.")
        thousands, decimals = grouped.group(1), grouped.group(2)
        separators = set(re.findall(r"[.,]", thousands))
        decimal_separator = cleaned[len(thousands)]
        # "1.234.56" or "1,234,56" would mix up the two roles.
        if len(separators) != 1 or decimal_separator in separators:
            raise AmountError("Importo non valido: usa un formato come 12,50.")
        whole = re.sub(r"[.,]", "", thousands)

    cents = int(whole) * 100 + int(decimals.ljust(2, "0") or "0")
    if cents <= 0:
        raise AmountError("L'importo deve essere maggiore di zero.")
    if cents > MAX_CENTS:
        raise AmountError("Importo troppo alto: controlla la cifra.")
    return cents


def format_cents(cents: int, decimal_separator: str = ".") -> str:
    """Format cents as a plain decimal string without thousands separators."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}{decimal_separator}{cents % 100:02d}"
