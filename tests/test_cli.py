"""Recovery command line: reset a password when nobody can sign in."""

from __future__ import annotations

import pytest

from app import cli

from .conftest import FABIO


def test_reset_password_from_cli(client, anon):
    assert cli.reset_password("  FABIO ", password="nuova-password-1") == 0

    # The old session is gone, the old password no longer works.
    assert client.get("/api/v1/auth/me").status_code == 401
    old = anon.post("/api/v1/auth/login", json={"username": "fabio", "password": FABIO["password"]})
    assert old.status_code == 401
    new = anon.post("/api/v1/auth/login", json={"username": "fabio", "password": "nuova-password-1"})
    assert new.status_code == 200


def test_reset_password_unknown_user(client):
    with pytest.raises(SystemExit) as stop:
        cli.reset_password("mario", password="nuova-password-1")
    assert "non trovato" in str(stop.value)


def test_ask_password_must_match(monkeypatch):
    answers = iter(["password-uno", "password-due"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))
    with pytest.raises(SystemExit) as stop:
        cli._ask_password()
    assert "non coincidono" in str(stop.value)


def test_ask_password_too_short(monkeypatch):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "corta")
    with pytest.raises(SystemExit):
        cli._ask_password()


def test_list_users(client, capsys):
    assert cli.list_users() == 0
    out = capsys.readouterr().out
    assert "fabio\tFabio" in out and "nastia\tNastia" in out
