"""Command-line recovery tools, run inside the container.

    docker compose exec spese python -m app.cli list-users
    docker compose exec spese python -m app.cli reset-password fabio

`reset-password` is the last resort when nobody can sign in (both
passwords forgotten). It asks for the new password twice, without echo,
and signs that user out of every device.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from .config import get_settings
from .db import connect, migrate
from .security import hash_password

MIN_PASSWORD = 8


def _open():
    settings = get_settings()
    if not settings.db_path.exists():
        sys.exit(f"Database non trovato in {settings.db_path}.")
    conn = connect(settings.db_path)
    migrate(conn)
    return conn


def list_users() -> int:
    conn = _open()
    try:
        rows = conn.execute("SELECT username, display_name FROM users ORDER BY id").fetchall()
    finally:
        conn.close()
    if not rows:
        print("Nessun utente: apri l'app per la configurazione iniziale.")
    for row in rows:
        print(f"{row['username']}\t{row['display_name']}")
    return 0


def _ask_password() -> str:
    first = getpass.getpass("Nuova password: ")
    if len(first) < MIN_PASSWORD:
        sys.exit(f"La password deve avere almeno {MIN_PASSWORD} caratteri.")
    if getpass.getpass("Ripeti la password: ") != first:
        sys.exit("Le due password non coincidono. Nessuna modifica fatta.")
    return first


def reset_password(name: str, password: str | None = None) -> int:
    key = " ".join(name.split()).casefold()
    conn = _open()
    try:
        row = conn.execute(
            "SELECT id, display_name FROM users WHERE username = ?", (key,)
        ).fetchone()
        if row is None:
            names = ", ".join(r[0] for r in conn.execute("SELECT username FROM users ORDER BY id"))
            sys.exit(f"Utente «{name}» non trovato. Utenti esistenti: {names or 'nessuno'}.")
        if password is None:
            password = _ask_password()
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), row["id"])
        )
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
        conn.commit()
    finally:
        conn.close()
    print(f"Password di {row['display_name']} reimpostata. Accedi di nuovo dall'app.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Strumenti di recupero.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-users", help="Elenca gli utenti")
    reset = commands.add_parser("reset-password", help="Reimposta la password di un utente")
    reset.add_argument("name", help="Nome dell'utente, es. fabio")
    args = parser.parse_args(argv)
    if args.command == "list-users":
        return list_users()
    return reset_password(args.name)


if __name__ == "__main__":
    raise SystemExit(main())
