"""Tray icon rendering (Pillow)."""
from __future__ import annotations

from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .model import Usage

SIZE = 64
GREY, BLUE, ORANGE, RED = (90, 90, 90), (37, 99, 235), (225, 130, 0), (200, 40, 40)


def colour(pct: Optional[float]) -> tuple:
    if pct is None:
        return GREY
    if pct >= 90:
        return RED
    if pct >= 70:
        return ORANGE
    return BLUE


def _font(size: int):
    for name in ("arialbd.ttf", "segoeuib.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _label(pct: Optional[float]) -> str:
    return "--" if pct is None else str(int(round(min(pct, 99.4)) if pct < 100 else 100))


def make_icon(usage: Optional[Usage], mode: str, stale: bool = False) -> Image.Image:
    """Icon for the current usage. `mode`: 'both' (two bars), 'session' or 'weekly' (one number)."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    session = usage.session.pct if usage and usage.session else None
    weekly = usage.weekly.pct if usage and usage.weekly else None

    if usage is None:
        draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), 12, fill=GREY)
        draw.text((SIZE / 2, SIZE / 2), "!", font=_font(48), fill="white", anchor="mm")
        return img

    if mode in ("session", "weekly"):
        value = session if mode == "session" else weekly
        text = _label(value)
        draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), 12, fill=colour(value))
        draw.text((SIZE / 2, SIZE / 2), text, font=_font(44 if len(text) < 3 else 34), fill="white", anchor="mm")
    else:
        draw.rounded_rectangle((0, 0, SIZE - 1, SIZE // 2 - 1), 8, fill=colour(session))
        draw.rounded_rectangle((0, SIZE // 2, SIZE - 1, SIZE - 1), 8, fill=colour(weekly))
        for row, value in enumerate((session, weekly)):
            text = _label(value)
            draw.text((SIZE / 2, SIZE / 4 + row * SIZE / 2), text,
                      font=_font(30 if len(text) < 3 else 24), fill="white", anchor="mm")
    if stale:  # small hollow marker: the shown values are old
        draw.ellipse((SIZE - 20, SIZE - 20, SIZE - 3, SIZE - 3), fill=(30, 30, 30), outline="white", width=3)
    return img
