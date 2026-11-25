"""The text that goes with the CSV files of an export (0.14.0, "Per Claude";
from 0.15.0 every export of Impostazioni → Esporta CSV: spese, entrate,
articoli Vinted or «Tutto»).

The app never calls anything outside: it downloads the files and copies
this text, the person attaches and pastes them in their own chat. The text
says what the files hold, gives the totals to check them against (so the
assistant can tell it read every row) and explains the conventions of the
app that the columns alone do not tell: meal vouchers, the Vinted category,
planned expenses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

MONTHS = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


def euro(cents: int, signed: bool = False) -> str:
    """"2.425,54 €", as the app shows it; with ``signed`` "+1.487,79 €"."""
    sign = "−" if cents < 0 else ("+" if signed else "")
    whole, rest = divmod(abs(cents), 100)
    return f"{sign}{whole:,}".replace(",", ".") + f",{rest:02d} €"


def day_text(day: date) -> str:
    """"1° novembre 2026", "25 novembre 2026"."""
    number = "1°" if day.day == 1 else str(day.day)
    return f"{number} {MONTHS[day.month - 1]} {day.year}"


def period_text(month: str | None, start: date | None, end: date | None) -> str:
    if month:
        year, number = (int(part) for part in month.split("-"))
        return f"{MONTHS[number - 1]} {year}"
    if start and end:
        return f"dal {day_text(start)} al {day_text(end)}"
    if start:
        return f"dal {day_text(start)} in poi"
    if end:
        return f"fino al {day_text(end)}"
    return "tutti i movimenti registrati"


def _count(number: int, one: str, many: str) -> str:
    return f"{number} {one if number == 1 else many}"


@dataclass
class Movements:
    """Expenses or incomes of the period. ``file`` is None when there are
    none (the file is then left out)."""

    file: str | None
    count: int
    cents: int
    planned_count: int = 0  # expenses only: dated after today
    planned_cents: int = 0
    voucher_cents: int = 0  # incomes only: meal vouchers


@dataclass
class VintedItems:
    """Every Vinted item (no period: they live for months)."""

    file: str | None
    count: int
    by_status: dict[str, int]  # label → count, in display order, zeros left out
    paid_cents: int
    sold_cents: int
    gain_cents: int


def _plural_items(number: int) -> str:
    return _count(number, "articolo", "articoli")


def build_brief(
    *,
    period: str,
    expenses: Movements | None,
    incomes: Movements | None,
    vinted: VintedItems | None,
    excel: bool,
    vinted_category: str | None,
    vinted_income_category: str,
    voucher_category: str,
) -> str:
    """The text for the parts that were asked for: a part that is None was
    not asked for and is not mentioned; one asked for and empty says so."""
    lines = [f"Dati di «Spese di Casa», l'app delle spese della nostra famiglia: {period}.", ""]
    lines.append("File allegati:")
    if expenses is not None:
        if expenses.file:
            lines.append(
                f"- {expenses.file}: {_count(expenses.count, 'spesa', 'spese')}, "
                f"totale {euro(expenses.cents)}."
            )
        else:
            lines.append("- Nessuna spesa registrata nel periodo.")
    if incomes is not None:
        if incomes.file:
            vouchers = f", di cui {euro(incomes.voucher_cents)} in buoni pasto" if incomes.voucher_cents else ""
            lines.append(
                f"- {incomes.file}: {_count(incomes.count, 'entrata', 'entrate')}, totale "
                f"{euro(incomes.cents)}{vouchers}."
            )
        else:
            lines.append("- Nessuna entrata registrata nel periodo.")
    if vinted is not None:
        if vinted.file:
            states = ", ".join(f"{count} {label.lower()}" for label, count in vinted.by_status.items())
            lines.append(
                f"- {vinted.file}: {_plural_items(vinted.count)} Vinted, tutti quelli registrati "
                f"(non solo del periodo): {states}. Pagati {euro(vinted.paid_cents)}, "
                f"venduti {euro(vinted.sold_cents)}, guadagno sui venduti "
                f"{euro(vinted.gain_cents, signed=True)}."
            )
        else:
            lines.append("- Nessun articolo Vinted registrato.")
    if expenses is not None and incomes is not None and incomes.count:
        lines.append(f"Entrate meno spese: {euro(incomes.cents - expenses.cents, signed=True)}.")

    lines += [
        "",
        "Prima di tutto controlla di aver letto tutte le righe: numero e totali devono "
        "coincidere con questi.",
        "",
        "Come leggere i file:",
    ]
    if excel:
        lines.append(
            "- Formato «Excel italiano»: separatore punto e virgola, virgola decimale. Una riga "
            "per movimento o articolo; importi in euro, sempre positivi tranne il guadagno; "
            "date nel formato AAAA-MM-GG."
        )
    else:
        lines.append(
            "- Una riga per movimento o articolo. Importi in euro, sempre positivi tranne il "
            "guadagno, con il punto decimale; date nel formato AAAA-MM-GG."
        )
    if expenses is not None or incomes is not None:
        lines.append(
            "- pagato_da (spese) e ricevuto_da (entrate): chi ha pagato o ricevuto; inserito_da: "
            "chi l'ha registrato nell'app; creato_il: quando, in UTC."
        )
    if incomes is not None or expenses is not None:
        lines.append(
            f"- Buoni pasto: sono un'entrata della categoria «{voucher_category}». Gli acquisti "
            "pagati con i buoni sono spese normali, per intero, nella loro categoria."
        )
    if vinted_category and (expenses is not None or incomes is not None):
        lines.append(
            f"- Categoria «{vinted_category}» delle spese: articoli comprati per rivenderli su "
            f"Vinted e costi delle vendite (spedizioni, buste). Le vendite sono entrate della "
            f"categoria «{vinted_income_category}»."
        )
    if vinted is not None and vinted.file:
        lines.append(
            "- Articoli Vinted: guadagno = prezzo di vendita meno prezzo di acquisto (tutto il "
            "prezzo per le cose che avevamo già in casa), vuoto finché l'articolo non è venduto; "
            "giorni_in_vendita dalla pubblicazione alla vendita o a oggi. L'acquisto e la vendita "
            "di ogni articolo sono anche, rispettivamente, una spesa e un'entrata."
        )
    if expenses is not None and expenses.planned_count:
        lines.append(
            f"- {_count(expenses.planned_count, 'spesa ha', 'spese hanno')} una data futura "
            f"({euro(expenses.planned_cents)} in tutto): sono previste (addebiti già noti) e non ancora "
            "pagate, ma contano già nel loro mese."
        )
    return "\n".join(lines) + "\n"
