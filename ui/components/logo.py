"""Load the HAPPY logo PNG as a CTkImage scaled to a target width.

Returns None when the asset is missing or PIL can't open it. Callers
fall back to a CTkLabel with the brand name as plain text.
"""
from __future__ import annotations

from typing import Optional

import customtkinter as ctk
from PIL import Image

from core import config


def load_logo_image(target_width: int = 180) -> Optional[ctk.CTkImage]:
    try:
        if not config.LOGO_PNG.exists():
            return None
        img = Image.open(config.LOGO_PNG)
        w, h = img.size
        new_h = max(1, int(round(target_width * h / w)))
        return ctk.CTkImage(
            light_image=img, dark_image=img, size=(target_width, new_h)
        )
    except Exception:
        return None
