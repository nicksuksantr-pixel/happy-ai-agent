"""Small inline pill — colored badge with a dot + label.

Used for: auth status (Connected / Not connected), quota meters
(RPD 23/500), session status, etc. Compact, single-line.
"""
from __future__ import annotations

import customtkinter as ctk

from ui import theme


def pill(parent, *, text: str, color: str = None,
         bg: str = None) -> ctk.CTkFrame:
    color = color or theme.TEXT_SUB
    bg = bg or theme.BG_CARD_HOVER

    frame = ctk.CTkFrame(
        parent, fg_color=bg,
        corner_radius=theme.RADIUS_PILL,
    )

    dot = ctk.CTkFrame(
        frame, fg_color=color,
        width=8, height=8, corner_radius=4,
    )
    dot.grid(row=0, column=0, padx=(10, 6), pady=6)

    ctk.CTkLabel(
        frame, text=text,
        font=theme.FONT_TINY, text_color=color,
        anchor="w",
    ).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=4)

    return frame
