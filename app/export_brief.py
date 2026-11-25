"""The text that goes with the CSV files sent to an AI assistant (0.14.0,
"Per Claude" in Impostazioni → Esporta CSV).

The app never calls anything outside: it downloads the files and copies
this text, the person attaches and pastes them in their own chat. The text
says what the files hold, gives the totals to check them against (so the
assistant can tell it read every row) and explains the conventions of the
app that the columns alone do not tell: meal vouchers, the Vinted category,
planned expenses.
"""

from __future__ import annotations

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


def build_brief(
    *,
    period: str,
    expense_file: str | None,
    expense_count: int,
    expense_cents: int,
    planned_count: int,
    planned_cents: int,
    income_file: str | None,
    income_count: int,
    income_cents: int,
    voucher_cents: int,
    vinted_category: str | None,
    vinted_income_category: str,
    voucher_category: str,
) -> str:
    lines = [f"Dati di «Spese di Casa», l'app delle spese della nostra famiglia: {period}.", ""]

    if expense_file or income_file:
        lines.append("File allegati:")
    if expense_file:
        lines.append(
            f"- {expense_file}: {_count(expense_count, 'spesa', 'spese')}, totale {euro(expense_cents)}."
        )
    else:
        lines.append("- Nessuna spesa registrata nel periodo.")
    if income_file:
        vouchers = f", di cui {euro(voucher_cents)} in buoni pasto" if voucher_cents else ""
        lines.append(
            f"- {income_file}: {_count(income_count, 'entrata', 'entrate')}, totale "
            f"{euro(income_cents)}{vouchers}."
        )
    else:
        lines.append("- Nessuna entrata registrata nel periodo.")
    if income_count:
        lines.append(f"Entrate meno spese: {euro(income_cents - expense_cents, signed=True)}.")
    lines += [
        "",
        "Prima di tutto controlla di aver letto tutte le righe: numero e totali devono "
        "coincidere con questi.",
        "",
        "Come leggere i file:",
        "- Una riga per movimento. Importi in euro, sempre positivi, con il punto decimale; "
        "date nel formato AAAA-MM-GG.",
        "- pagato_da (spese) e ricevuto_da (entrate): chi ha pagato o ricevuto; inserito_da: "
        "chi l'ha registrato nell'app; creato_il: quando, in UTC.",
        f"- Buoni pasto: sono un'entrata della categoria «{voucher_category}». Gli acquisti "
        "pagati con i buoni sono spese normali, per intero, nella loro categoria.",
    ]
    if vinted_category:
        lines.append(
            f"- Categoria «{vinted_category}» delle spese: articoli comprati per rivenderli su "
            f"Vinted e costi delle vendite (spedizioni, buste). Le vendite sono entrate della "
            f"categoria «{vinted_income_category}»."
        )
    if planned_count:
        lines.append(
            f"- {_count(planned_count, 'spesa ha', 'spese hanno')} una data futura "
            f"({euro(planned_cents)} in tutto): sono previste (addebiti già noti) e non ancora "
            "pagate, ma contano già nel loro mese."
        )
    return "\n".join(lines) + "\n"
