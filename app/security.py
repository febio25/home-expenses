"""Password hashing, sessions and the authentication dependency."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response

from .config import SESSION_COOKIE, Settings, get_settings
from .db import get_db, utc_now

# scrypt from the standard library: no extra dependency. N=2^15, r=8, p=1
# needs about 32 MiB and roughly 0.1-0.3 s per login, fine for two users.
_SCRYPT_LOG_N = 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 128 * 1024 * 1024

MIN_PASSWORD_LENGTH = 8
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Sent by our frontend on every write. A cross-site page cannot add a custom
# header without a CORS preflight, which this app never grants.
CSRF_HEADER = "x-requested-with"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**_SCRYPT_LOG_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
        dklen=32,
    )
    return f"scrypt${_SCRYPT_LOG_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, log_n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2 ** int(log_n),
            r=int(r),
            p=int(p),
            maxmem=_SCRYPT_MAXMEM,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", "ignore")).hexdigest()


def _expiry(settings: Settings) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=settings.session_days)
    return expires.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_session(conn: sqlite3.Connection, user_id: int, settings: Settings) -> str:
    """Create a session and return the raw token (stored only as a hash)."""
    token = secrets.token_urlsafe(32)
    now = utc_now()
    conn.execute(
        "INSERT INTO sessions (user_id, token_hash, created_at, last_seen_at, expires_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, hash_token(token), now, now, _expiry(settings)),
    )
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    return token


def _is_https(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return forwarded == "https" or request.url.scheme == "https"


def set_session_cookie(response: Response, request: Request, token: str, settings: Settings) -> None:
    if settings.cookie_secure == "auto":
        secure = _is_https(request)
    else:
        secure = settings.cookie_secure == "true"
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def read_token(request: Request) -> tuple[str | None, bool]:
    """Return (token, came_from_cookie). Bearer is for a future native app."""
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None, False
    cookie = request.cookies.get(SESSION_COOKIE)
    return (cookie or None), True


def current_user(
    request: Request,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row:
    """Authenticate the request and slide the session expiry forward."""
    settings = get_settings()
    token, from_cookie = read_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Accesso richiesto.")
    if from_cookie and request.method not in SAFE_METHODS and CSRF_HEADER not in request.headers:
        raise HTTPException(status_code=403, detail="Richiesta non valida.")

    now = utc_now()
    row = db.execute(
        "SELECT s.id AS session_id, s.last_seen_at, u.id, u.username, u.display_name"
        " FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.token_hash = ? AND s.expires_at > ?",
        (hash_token(token), now),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Sessione scaduta: accedi di nuovo.")

    # Renew at most once a day, so reads do not write on every request.
    if row["last_seen_at"][:10] != now[:10]:
        db.execute(
            "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE id = ?",
            (now, _expiry(settings), row["session_id"]),
        )
        db.commit()
        if from_cookie:
            set_session_cookie(response, request, token, settings)
    return row


class LoginThrottle:
    """Small in-memory brake against password guessing.

    After MAX_FAILURES wrong passwords for a username within WINDOW seconds,
    further attempts are refused until the window has passed.
    """

    MAX_FAILURES = 5
    WINDOW = 300

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}

    def _recent(self, key: str) -> list[float]:
        cutoff = time.monotonic() - self.WINDOW
        recent = [t for t in self._failures.get(key, []) if t > cutoff]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def is_blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.MAX_FAILURES

    def record_failure(self, key: str) -> None:
        self._failures.setdefault(key, []).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
