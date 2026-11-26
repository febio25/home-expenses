"""Vinted section: the photo of an item (0.8.0), full size and as a
thumbnail, stored in the database as JPEG sent by the phone, already
reduced. Split from vinted.py in 0.17.0; same addresses."""

from __future__ import annotations

import base64
import binascii
import hashlib
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..db import get_db, utc_now
from ..security import current_user
from ..vinted_schemas import VintedItemOut, VintedPhotoIn
from .vinted import _item_row, fetch_item

router = APIRouter(prefix="/vinted", tags=["vinted"])

MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_THUMB_BYTES = 300 * 1024
JPEG_MAGIC = b"\xff\xd8\xff"


def _decode_jpeg(text: str, limit: int, what: str) -> bytes:
    try:
        data = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"{what} non valida.") from error
    if not data.startswith(JPEG_MAGIC):
        raise HTTPException(status_code=422, detail=f"{what}: serve un'immagine JPEG.")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"{what} troppo grande.")
    return data


@router.put("/items/{item_id}/photo", response_model=VintedItemOut)
def put_photo(
    item_id: int,
    body: VintedPhotoIn,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Set or replace the photo. The client sends it already resized (the
    app: about 1200 px and a 160 px thumbnail, JPEG, no location data)."""
    _item_row(db, item_id)
    image = _decode_jpeg(body.image, MAX_IMAGE_BYTES, "Foto")
    thumb = _decode_jpeg(body.thumb, MAX_THUMB_BYTES, "Miniatura")
    token = hashlib.sha256(image).hexdigest()[:16]
    now = utc_now()
    db.execute(
        "INSERT INTO vinted_photos (item_id, token, created_at, image, thumb) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(item_id) DO UPDATE SET token = excluded.token,"
        " created_at = excluded.created_at, image = excluded.image, thumb = excluded.thumb",
        (item_id, token, now, image, thumb),
    )
    db.execute("UPDATE vinted_items SET updated_at = ? WHERE id = ?", (now, item_id))
    db.commit()
    return fetch_item(db, item_id)


def _photo(db: sqlite3.Connection, item_id: int, column: str, version: str | None) -> Response:
    row = db.execute(
        f"SELECT token, {column} AS data FROM vinted_photos WHERE item_id = ?", (item_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Foto non trovata.")
    # The app asks with ?v=<token>: that address never changes content, so the
    # phone keeps it. Without (or with an old) token, always ask again.
    cache = "private, max-age=31536000, immutable" if version == row["token"] else "private, no-cache"
    return Response(
        content=row["data"],
        media_type="image/jpeg",
        headers={"Cache-Control": cache, "ETag": f'"{row["token"]}-{column}"'},
    )


@router.get(
    "/items/{item_id}/photo",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}},
)
def get_photo(
    item_id: int,
    v: str | None = Query(None, description="Photo token from the item: makes the image cacheable"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return _photo(db, item_id, "image", v)


@router.get(
    "/items/{item_id}/photo/thumb",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}},
)
def get_thumb(
    item_id: int,
    v: str | None = Query(None, description="Photo token from the item: makes the image cacheable"),
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return _photo(db, item_id, "thumb", v)


@router.delete("/items/{item_id}/photo", status_code=204)
def delete_photo(
    item_id: int,
    user: sqlite3.Row = Depends(current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _item_row(db, item_id)
    db.execute("DELETE FROM vinted_photos WHERE item_id = ?", (item_id,))
    db.execute("UPDATE vinted_items SET updated_at = ? WHERE id = ?", (utc_now(), item_id))
    db.commit()
