from fastapi.testclient import TestClient

from tests.conftest import CSRF, FABIO, NASTIA

API = "/api/v1"


def test_setup_then_login(anon):
    assert anon.get(f"{API}/setup/status").json() == {"needs_setup": True}

    created = anon.post(f"{API}/setup", json={"users": [FABIO, NASTIA]})
    assert created.status_code == 201
    assert [u["display_name"] for u in created.json()] == ["Fabio", "Nastia"]
    assert anon.get(f"{API}/setup/status").json() == {"needs_setup": False}

    # Setup is a one-shot: a second call must not create or replace users.
    again = anon.post(f"{API}/setup", json={"users": [{"name": "Eve", "password": "12345678"}]})
    assert again.status_code == 409

    assert anon.get(f"{API}/auth/me").status_code == 401
    login = anon.post(f"{API}/auth/login", json={"username": "fabio", "password": FABIO["password"]})
    assert login.status_code == 200
    assert anon.get(f"{API}/auth/me").json()["display_name"] == "Fabio"


def test_setup_rejects_duplicate_names_and_short_passwords(anon):
    same = anon.post(
        f"{API}/setup",
        json={"users": [FABIO, {"name": " fabio ", "password": "another-password"}]},
    )
    assert same.status_code == 422
    short = anon.post(f"{API}/setup", json={"users": [{"name": "Fabio", "password": "short"}]})
    assert short.status_code == 422
    assert anon.get(f"{API}/setup/status").json() == {"needs_setup": True}


def test_session_cookie_flags(anon):
    anon.post(f"{API}/setup", json={"users": [FABIO, NASTIA]})
    login = anon.post(f"{API}/auth/login", json={"username": "Fabio", "password": FABIO["password"]})
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert f"max-age={90 * 24 * 3600}" in cookie  # 90 days
    assert "secure" not in cookie  # disabled in the test configuration


def test_cookie_is_secure_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("SPESE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SPESE_COOKIE_SECURE", raising=False)
    from app.main import create_app

    with TestClient(create_app()) as client:
        client.post(f"{API}/setup", json={"users": [FABIO]})
        login = client.post(
            f"{API}/auth/login", json={"username": "Fabio", "password": FABIO["password"]}
        )
        assert "secure" in login.headers["set-cookie"].lower()


def test_cookie_secure_auto_follows_forwarded_proto(tmp_path, monkeypatch):
    monkeypatch.setenv("SPESE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SPESE_COOKIE_SECURE", "auto")
    from app.main import create_app

    credentials = {"username": "Fabio", "password": FABIO["password"]}
    with TestClient(create_app()) as client:
        client.post(f"{API}/setup", json={"users": [FABIO]})
        plain = client.post(f"{API}/auth/login", json=credentials)
        assert "secure" not in plain.headers["set-cookie"].lower()
        proxied = client.post(
            f"{API}/auth/login", json=credentials, headers={"X-Forwarded-Proto": "https"}
        )
        assert "secure" in proxied.headers["set-cookie"].lower()


def test_wrong_password_and_throttle(anon):
    anon.post(f"{API}/setup", json={"users": [FABIO, NASTIA]})
    for _ in range(5):
        bad = anon.post(f"{API}/auth/login", json={"username": "Fabio", "password": "wrong"})
        assert bad.status_code == 401
    # Blocked now, even with the right password.
    blocked = anon.post(
        f"{API}/auth/login", json={"username": "Fabio", "password": FABIO["password"]}
    )
    assert blocked.status_code == 429
    # The other user is not affected.
    other = anon.post(
        f"{API}/auth/login", json={"username": "Nastia", "password": NASTIA["password"]}
    )
    assert other.status_code == 200


def test_every_data_endpoint_requires_login(anon):
    anon.post(f"{API}/setup", json={"users": [FABIO, NASTIA]})
    for path in (
        "/expenses",
        "/categories",
        "/merchants",
        "/summary?month=2026-11",
        "/export.csv?month=2026-11",
        "/backup",
        "/users",
    ):
        assert anon.get(f"{API}{path}").status_code == 401, path
    assert anon.post(f"{API}/restore", content=b"x").status_code == 401
    assert anon.post(f"{API}/expenses", json={}).status_code == 401


def test_cookie_writes_need_the_csrf_header(app):
    with TestClient(app) as client:  # no default X-Requested-With
        client.post(f"{API}/setup", json={"users": [FABIO, NASTIA]})
        client.post(f"{API}/auth/login", json={"username": "Fabio", "password": FABIO["password"]})
        assert client.get(f"{API}/categories").status_code == 200
        forged = client.post(f"{API}/categories", json={"name": "Forged"})
        assert forged.status_code == 403
        allowed = client.post(f"{API}/categories", json={"name": "Legit"}, headers=CSRF)
        assert allowed.status_code == 201


def test_bearer_token_works_for_a_future_native_app(app):
    with TestClient(app) as client:
        client.post(f"{API}/setup", json={"users": [FABIO, NASTIA]})
        login = client.post(
            f"{API}/auth/login", json={"username": "Fabio", "password": FABIO["password"]}
        )
        token = login.cookies["spese_session"]
    with TestClient(app) as native:  # fresh client, no cookies
        headers = {"Authorization": f"Bearer {token}"}
        assert native.get(f"{API}/auth/me", headers=headers).json()["display_name"] == "Fabio"
        # Bearer requests are not exposed to CSRF, so no extra header is needed.
        created = native.post(f"{API}/categories", json={"name": "Da app"}, headers=headers)
        assert created.status_code == 201


def test_logout_invalidates_the_session(client):
    token = client.cookies["spese_session"]
    assert client.post(f"{API}/auth/logout").status_code == 200
    client.cookies.set("spese_session", token)
    assert client.get(f"{API}/auth/me").status_code == 401


def test_change_own_password(client):
    me = client.get(f"{API}/auth/me").json()
    wrong = client.put(
        f"{API}/users/{me['id']}/password",
        json={"new_password": "new-password-1", "current_password": "nope"},
    )
    assert wrong.status_code == 403
    ok = client.put(
        f"{API}/users/{me['id']}/password",
        json={"new_password": "new-password-1", "current_password": FABIO["password"]},
    )
    assert ok.status_code == 200
    assert client.get(f"{API}/auth/me").status_code == 200  # current session survives
    client.post(f"{API}/auth/logout")
    old = client.post(f"{API}/auth/login", json={"username": "Fabio", "password": FABIO["password"]})
    assert old.status_code == 401
    new = client.post(f"{API}/auth/login", json={"username": "Fabio", "password": "new-password-1"})
    assert new.status_code == 200


def test_reset_the_other_users_password(client, app):
    users = {u["display_name"]: u["id"] for u in client.get(f"{API}/users").json()}
    with TestClient(app, headers=CSRF) as nastia:
        nastia.post(f"{API}/auth/login", json={"username": "Nastia", "password": NASTIA["password"]})
        assert nastia.get(f"{API}/auth/me").status_code == 200

        reset = client.put(
            f"{API}/users/{users['Nastia']}/password", json={"new_password": "reset-by-fabio"}
        )
        assert reset.status_code == 200
        # Her old sessions are closed; the new password works.
        assert nastia.get(f"{API}/auth/me").status_code == 401
        again = nastia.post(
            f"{API}/auth/login", json={"username": "Nastia", "password": "reset-by-fabio"}
        )
        assert again.status_code == 200


def test_passwords_are_stored_hashed(client, tmp_path):
    import sqlite3

    conn = sqlite3.connect(tmp_path / "spese.db")
    hashes = [row[0] for row in conn.execute("SELECT password_hash FROM users")]
    tokens = [row[0] for row in conn.execute("SELECT token_hash FROM sessions")]
    conn.close()
    assert all(h.startswith("scrypt$") for h in hashes)
    assert FABIO["password"] not in "".join(hashes)
    assert client.cookies["spese_session"] not in tokens
