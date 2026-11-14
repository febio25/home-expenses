"""Runtime configuration, read from environment variables.

All settings are deployment plumbing (paths, cookie policy). Anything the
family configures (users, categories) lives in the database and is managed
from the app UI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DB_FILENAME = "spese.db"
SESSION_COOKIE = "spese_session"
MAX_RESTORE_BYTES = 50 * 1024 * 1024  # 50 MiB is far beyond years of expenses


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    # "true": always set the Secure flag (default, right behind HTTPS).
    # "auto": set it only when the request arrived over HTTPS.
    # "false": never (plain-HTTP tests on the LAN).
    cookie_secure: str
    session_days: int

    @property
    def db_path(self) -> Path:
        return self.data_dir / DB_FILENAME


def get_settings() -> Settings:
    cookie_secure = os.environ.get("SPESE_COOKIE_SECURE", "true").strip().lower()
    if cookie_secure not in {"true", "false", "auto"}:
        raise ValueError("SPESE_COOKIE_SECURE must be one of: true, false, auto")
    session_days = int(os.environ.get("SPESE_SESSION_DAYS", "90"))
    if session_days < 1:
        raise ValueError("SPESE_SESSION_DAYS must be at least 1")
    return Settings(
        data_dir=Path(os.environ.get("SPESE_DATA_DIR", "/data")),
        cookie_secure=cookie_secure,
        session_days=session_days,
    )
