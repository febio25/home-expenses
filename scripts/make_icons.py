"""Generate the PWA icons into app/static/icons/.

Development-only helper (needs Pillow); the generated PNGs are committed, so
the app and its Docker image never run this.

    python scripts/make_icons.py

The icon is a till receipt with a torn bottom edge and a euro sign.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"
GREEN = (11, 110, 79, 255)       # --primary
WHITE = (255, 255, 255, 255)
SCALE = 4                        # supersampling for smooth edges
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    raise SystemExit("No bold TrueType font found: add one to FONT_CANDIDATES.")


def _receipt(draw: ImageDraw.ImageDraw, size: int, content: float) -> None:
    """Draw the receipt centred, occupying `content` (0-1) of the canvas height."""
    height = size * content
    width = height * 0.74
    left = (size - width) / 2
    top = (size - height) / 2
    right = left + width
    bottom = top + height
    teeth = 6
    tooth_w = width / teeth
    tooth_h = tooth_w * 0.55
    radius = width * 0.07

    draw.rounded_rectangle([left, top, right, bottom - tooth_h], radius=radius, fill=WHITE)
    draw.rectangle([left, top + radius * 2, right, bottom - tooth_h], fill=WHITE)
    for index in range(teeth):
        x = left + index * tooth_w
        draw.polygon(
            [(x, bottom - tooth_h - 1), (x + tooth_w, bottom - tooth_h - 1), (x + tooth_w / 2, bottom)],
            fill=WHITE,
        )

    font = _font(int(height * 0.58))
    box = draw.textbbox((0, 0), "€", font=font)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    centre_y = top + (height - tooth_h) / 2
    draw.text(
        (left + (width - text_w) / 2 - box[0], centre_y - text_h / 2 - box[1]),
        "€",
        font=font,
        fill=GREEN,
    )


def _glyph(draw: ImageDraw.ImageDraw, size: int, kind: str) -> None:
    """Simple white symbols for the shortcut icons."""
    stroke = size * 0.09
    if kind == "plus":
        arm = size * 0.26
        centre = size / 2
        draw.rounded_rectangle(
            [centre - arm, centre - stroke / 2, centre + arm, centre + stroke / 2],
            radius=stroke / 2, fill=WHITE)
        draw.rounded_rectangle(
            [centre - stroke / 2, centre - arm, centre + stroke / 2, centre + arm],
            radius=stroke / 2, fill=WHITE)
    else:  # list
        for row in (0.34, 0.5, 0.66):
            y = size * row
            draw.ellipse(
                [size * 0.26 - stroke / 2, y - stroke / 2, size * 0.26 + stroke / 2, y + stroke / 2],
                fill=WHITE)
            draw.rounded_rectangle(
                [size * 0.38, y - stroke / 2, size * 0.76, y + stroke / 2],
                radius=stroke / 2, fill=WHITE)


def make(name: str, size: int, *, shape: str, content: float = 0.0, glyph: str | None = None) -> None:
    big = size * SCALE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if shape == "full":          # maskable: the launcher cuts its own shape
        draw.rectangle([0, 0, big, big], fill=GREEN)
    elif shape == "rounded":
        draw.rounded_rectangle([0, 0, big - 1, big - 1], radius=big * 0.22, fill=GREEN)
    else:                        # circle, for shortcuts
        draw.ellipse([0, 0, big - 1, big - 1], fill=GREEN)
    if glyph:
        _glyph(draw, big, glyph)
    else:
        _receipt(draw, big, content)
    image.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
    print(f"wrote {name}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make("icon-192.png", 192, shape="rounded", content=0.62)
    make("icon-512.png", 512, shape="rounded", content=0.62)
    # Maskable icons keep everything important inside the central safe zone
    # (a circle of 80% of the width), so the receipt is drawn smaller.
    make("icon-maskable-192.png", 192, shape="full", content=0.48)
    make("icon-maskable-512.png", 512, shape="full", content=0.48)
    make("shortcut-new.png", 96, shape="circle", glyph="plus")
    make("shortcut-list.png", 96, shape="circle", glyph="list")


if __name__ == "__main__":
    main()
