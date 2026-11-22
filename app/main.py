"""Application entry point: API under /api/v1, the PWA shell everywhere else."""

from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

from . import __version__
from .config import get_settings
from .db import connect, init_db
from .routers import (
    auth,
    backup,
    categories,
    expenses,
    export,
    incomes,
    merchants,
    recurring,
    recurring_incomes,
    summary,
    vinted,
)
from .security import LoginThrottle

STATIC_DIR = (Path(__file__).parent / "static").resolve()
API_PREFIX = "/api/v1"

# Everything is served from this origin: no CDN, no external call.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
NO_CACHE = {"Cache-Control": "no-cache"}
MEDIA_TYPES = {".webmanifest": "application/manifest+json"}


def _render_service_worker() -> str:
    """Fill the placeholders of sw.js: the shell file list and a build id.

    The build id is a hash of every static file, so any change to the
    frontend produces a different worker and installed apps refresh their
    cache on the next launch, with no version number to bump by hand.
    """
    files = sorted(
        path for path in STATIC_DIR.rglob("*") if path.is_file() and path.name != "sw.js"
    )
    digest = hashlib.sha256(__version__.encode())
    urls = ["/"]
    for path in files:
        relative = path.relative_to(STATIC_DIR).as_posix()
        digest.update(relative.encode())
        digest.update(path.read_bytes())
        if relative != "index.html":  # cached as "/"
            urls.append(f"/{relative}")
    source = (STATIC_DIR / "sw.js").read_text(encoding="utf-8")
    digest.update(source.encode())
    return source.replace("__BUILD_ID__", digest.hexdigest()[:12]).replace(
        "__SHELL_FILES__", json.dumps(urls)
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # creates the database on first start, applies migrations after updates
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Spese di Casa API",
        version=__version__,
        description=(
            "REST JSON API of the household expense tracker. The PWA uses only "
            "these endpoints. Authenticate with the session cookie set by "
            "POST /auth/login, or with the same token as a Bearer header. "
            "Cookie-authenticated writes must carry an X-Requested-With header."
        ),
        # The default Swagger/ReDoc pages load their assets from a CDN, which
        # this project forbids. The schema itself stays available.
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.login_throttle = LoginThrottle()

    for module in (
        auth, expenses, incomes, recurring, recurring_incomes, categories, merchants, summary,
        vinted, export, backup,
    ):
        app.include_router(module.router, prefix=API_PREFIX)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = sorted({str(error["loc"][-1]) for error in exc.errors() if error.get("loc")})
        detail = "Dati non validi" + (f": {', '.join(fields)}." if fields else ".")
        return JSONResponse(status_code=422, content={"detail": detail, "fields": fields})

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        conn = connect(get_settings().db_path)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        return {"status": "ok", "version": __version__}

    service_worker_source = _render_service_worker()

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return Response(service_worker_source, media_type="text/javascript", headers=NO_CACHE)

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        """Static files, with index.html as fallback for the app's own routes."""
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Non trovato.")
        if path:
            candidate = (STATIC_DIR / path).resolve()
            if candidate.is_file() and STATIC_DIR in candidate.parents:
                return FileResponse(
                    candidate, headers=NO_CACHE, media_type=MEDIA_TYPES.get(candidate.suffix)
                )
            if "." in path.rsplit("/", 1)[-1]:
                raise HTTPException(status_code=404, detail="Non trovato.")
        return FileResponse(STATIC_DIR / "index.html", headers=NO_CACHE)

    return app


app = create_app()
