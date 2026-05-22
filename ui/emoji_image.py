"""Pillow color-emoji renderer for Tk.

Tk on Windows draws emoji as monochrome outlines because GDI ignores
COLR/CPAL tables. Workaround: render the glyph through Pillow with
`embedded_color=True` (Segoe UI Emoji), wrap as `CTkImage`, use via
`image=`. Falls back gracefully if the font isn't installed.

Lifted from ENA Conquest Desktop's `ui/emoji_image.py` per the new
desktop project playbook (section "Color emoji").
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont


_EMOJI_FONT_PATHS = [
    Path("C:/Windows/Fonts/seguiemj.ttf"),
    Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
]


def _find_emoji_font() -> Optional[Path]:
    for p in _EMOJI_FONT_PATHS:
        if p.exists():
            return p
    return None


@lru_cache(maxsize=128)
def _render_raw(char: str) -> Optional[Image.Image]:
    """Render at 109 px with color tables, crop to bbox, pad 4 px around
    so LANCZOS down-resize keeps an antialias headroom (otherwise edges
    look chopped at ~12-16 px)."""
    font_path = _find_emoji_font()
    if not font_path:
        return None
    try:
        font = ImageFont.truetype(str(font_path), 109)
    except Exception:
        return None
    canvas = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    try:
        draw.text((10, 10), char, font=font, embedded_color=True)
    except Exception:
        return None
    bbox = canvas.getbbox()
    if bbox is None:
        return None
    cropped = canvas.crop(bbox)
    padded = Image.new(
        "RGBA",
        (cropped.width + 8, cropped.height + 8),
        (0, 0, 0, 0),
    )
    padded.paste(cropped, (4, 4))
    return padded


@lru_cache(maxsize=256)
def emoji_for(char: str, size_px: int) -> Optional[ctk.CTkImage]:
    """Return a CTkImage of `char` sized to `size_px` (longest edge).
    None when no emoji font is installed; callers fall back to text."""
    raw = _render_raw(char)
    if raw is None:
        return None
    scale = size_px / max(raw.size)
    sized = raw.resize(
        (max(1, int(raw.width * scale)),
         max(1, int(raw.height * scale))),
        Image.LANCZOS,
    )
    return ctk.CTkImage(light_image=sized, dark_image=sized, size=sized.size)


def emoji_label(parent, char: str, *, size_px: int = 14):
    """A CTkLabel showing `char` as a color image, falling back to plain
    Segoe UI Emoji text if Pillow rasterization fails."""
    img = emoji_for(char, size_px)
    if img is not None:
        return ctk.CTkLabel(parent, image=img, text="")
    return ctk.CTkLabel(
        parent, text=char,
        font=("Segoe UI Emoji", size_px),
    )
