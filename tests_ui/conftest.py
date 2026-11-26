"""Interface tests (0.14.0): the app in a real Chrome at phone size, driven
by Playwright, against a real server started on a free port with an empty
data folder.

Run with:  pytest tests_ui
First time: python -m playwright install chromium
A Chrome already on the machine can be used instead of Playwright's:
SPESE_UI_CHROME=/path/to/chrome pytest tests_ui

Development only: Playwright is in requirements-dev.txt, never in the image.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import sync_playwright

# 0.17.0: the tests, the server they start and the browser (Europe/Rome,
# see open_phone) share one calendar. Before, between midnight in Italy and
# midnight UTC an expense prepared «today» by a test fell on the browser's
# yesterday, and the duplicate warning did not appear.
os.environ["TZ"] = "Europe/Rome"
time.tzset()

ROOT = Path(__file__).resolve().parent.parent
USERS = [{"name": "Fabio", "password": "password-fabio"}, {"name": "Nastia", "password": "password-nastia"}]
PHONES = {"360": {"width": 360, "height": 740}, "320": {"width": 320, "height": 640}}
# Errors the browser prints on purpose: the 401 of /auth/me before the
# login, the requests a test cuts to play "no network".
EXPECTED_CONSOLE = ("401", "ERR_INTERNET_DISCONNECTED", "ERR_FAILED")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    """A fresh app with its two users, at a base URL."""
    port = _free_port()
    env = {**os.environ, "SPESE_DATA_DIR": str(tmp_path), "SPESE_COOKIE_SECURE": "false"}
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20
    while True:
        try:
            if httpx.get(f"{base}/healthz", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            process.kill()
            raise RuntimeError("the app did not start")
        time.sleep(0.1)
    httpx.post(f"{base}/api/v1/setup", json={"users": USERS}).raise_for_status()
    try:
        yield base
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture
def api(server):
    """An API client signed in as Fabio, to prepare data quickly."""
    with httpx.Client(base_url=f"{server}/api/v1", headers={"X-Requested-With": "test"}) as client:
        client.post("/auth/login", json={"username": "Fabio", "password": USERS[0]["password"]}).raise_for_status()
        yield client


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        executable = os.environ.get("SPESE_UI_CHROME") or None
        browser = playwright.chromium.launch(executable_path=executable, args=["--no-sandbox"])
        yield browser
        browser.close()


def open_phone(browser, server, size="360"):
    """A phone-sized Chrome page signed in as Fabio, on "Nuova spesa"."""
    context = browser.new_context(
        viewport=PHONES[size], device_scale_factor=2, is_mobile=True, has_touch=True,
        locale="it-IT", timezone_id="Europe/Rome", accept_downloads=True,
    )
    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server)
    page = context.new_page()
    page.console_errors = []
    page.on("console", lambda message: page.console_errors.append(message.text)
            if message.type == "error" else None)
    page.on("pageerror", lambda error: page.console_errors.append(str(error)))
    page.goto(f"{server}/login")
    page.fill("#login-name", "Fabio")
    page.fill("#login-password", USERS[0]["password"])
    page.keyboard.press("Enter")
    page.wait_for_selector("#expense-amount")
    return page


@pytest.fixture
def phone(browser, server):
    page = open_phone(browser, server)
    yield page
    page.context.close()


def unexpected_errors(page):
    return [text for text in page.console_errors if not any(mark in text for mark in EXPECTED_CONSOLE)]
