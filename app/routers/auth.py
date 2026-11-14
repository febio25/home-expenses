"""First-run setup, login/logout and user passwords."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..config import get_settings
from ..db import get_db, utc_now
from ..schemas import (
    LoginIn,
    MessageOut,
    PasswordChangeIn,
    SetupIn,
    SetupStatus,
    UserOut,
)
from ..security import (
    clear_session_cookie,
    create_session,
    current_user,
    hash_password,
    hash_token,
    read_token,
    set_session_cookie,
    verify_password,
)

router = APIRouter(tags=["auth"])


def _clean_name(name: str) -> str:
    return " ".join(name.split())


def _user_count(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]


@router.get("/setup/status", response_model=SetupStatus)
def setup_status(db: sqlite3.Connection = Depends(get_db)):
    return {"needs_setup": _user_count(db) == 0}


@router.post("/setup", response_model=list[UserOut], status_code=201)
def setup(body: SetupIn, db: sqlite3.Connection = Depends(get_db)):
    """Create the household users. Works only while no user exists."""
    names = [_clean_name(user.name) for user in body.users]
    if any(not name for name in names):
        raise HTTPException(status_code=422, detail="Il nome non può essere vuoto.")
    if len({name.casefold() for name in names}) != len(names):
        raise HTTPException(status_code=422, detail="I due nomi devono essere diversi.")

    # BEGIN IMMEDIATE takes the write lock before the check, so two
    # simultaneous setup requests cannot both pass it.
    db.execute("BEGIN IMMEDIATE")
    if _user_count(db) > 0:
        raise HTTPException(status_code=409, detail="La configurazione iniziale è già stata fatta.")
    now = utc_now()
    for name, user in zip(names, body.users):
        db.execute(
            "INSERT INTO users (username, display_name, password_hash, created_at)"
            " VALUES (?, ?, ?, ?)",
            (name.casefold(), name, hash_password(user.password), now),
        )
    db.commit()
    rows = db.execute("SELECT id, display_name FROM users ORDER BY id").fetchall()
    return [dict(row) for row in rows]


@router.post("/auth/login", response_model=UserOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
):
    throttle = request.app.state.login_throttle
    key = _clean_name(body.username).casefold()
    if throttle.is_blocked(key):
        raise HTTPException(
            status_code=429,
            detail="Troppi tentativi sbagliati. Riprova tra qualche minuto.",
        )
    row = db.execute(
        "SELECT id, display_name, password_hash FROM users WHERE username = ?", (key,)
    ).fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        throttle.record_failure(key)
        raise HTTPException(status_code=401, detail="Nome o password non corretti.")
    throttle.reset(key)

    settings = get_settings()
    token = create_session(db, row["id"], settings)
    db.commit()
    set_session_cookie(response, request, token, settings)
    return {"id": row["id"], "display_name": row["display_name"]}


@router.post("/auth/logout", response_model=MessageOut)
def logout(request: Request, response: Response, db: sqlite3.Connection = Depends(get_db)):
    token, _ = read_token(request)
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
        db.commit()
    clear_session_cookie(response)
    return {"detail": "Disconnesso."}


@router.get("/auth/me", response_model=UserOut)
def me(user: sqlite3.Row = Depends(current_user)):
    return {"id": user["id"], "display_name": user["display_name"]}


@router.get("/users", response_model=list[UserOut], tags=["users"])
def list_users(
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    rows = db.execute("SELECT id, display_name FROM users ORDER BY id").fetchall()
    return [dict(row) for row in rows]


@router.put("/users/{user_id}/password", response_model=MessageOut, tags=["users"])
def change_password(
    user_id: int,
    body: PasswordChangeIn,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Change your own password, or reset the other household member's.

    Changing your own requires the current password. Resetting the other
    user's does not: it is the recovery path when a password is forgotten.
    """
    target = db.execute(
        "SELECT id, password_hash FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if target is None:
        raise HTTPException(status_code=404, detail="Utente non trovato.")

    own = target["id"] == user["id"]
    if own and not (
        body.current_password and verify_password(body.current_password, target["password_hash"])
    ):
        raise HTTPException(status_code=403, detail="La password attuale non è corretta.")

    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(body.new_password), user_id),
    )
    # Sign the target out everywhere else; keep the session making this call.
    db.execute(
        "DELETE FROM sessions WHERE user_id = ? AND id != ?",
        (user_id, user["session_id"]),
    )
    db.commit()
    return {"detail": "Password aggiornata."}
