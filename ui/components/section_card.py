"""Titled card with an accent header line.

Used by Settings, Dashboard stats, and any "named region" on a page.
Returns the *content* frame for the caller to populate; the title bar
is already gridded inside the card.

v2.3.0 — accepts an `emoji` argument for a color-emoji icon next to
the title. The emoji renders via Pillow (ui.emoji_image), falling
back to text-only when the emoji font is unavailable.
"""
from __future__ import annotations

import customtkinter as ctk

from ui import theme
from ui.emoji_image import emoji_for


def section_card(parent, *, title: str, accent: str = None,
                 emoji: str = "", emoji_size: int = 18,
                 row: int = 0, column: int = 0, columnspan: int = 1,
                 padx: tuple | int = 0, pady: tuple | int = 8,
                 sticky: str = "ew") -> ctk.CTkFrame:
    """Build the card, return the inner content frame."""
    accent = accent or theme.ACCENT

    card = ctk.CTkFrame(
        parent,
        fg_color=theme.BG_CARD,
        border_color=theme.BORDER_DIM,
        border_width=1,
        corner_radius=theme.RADIUS_CARD,
    )
    card.grid(row=row, column=column, columnspan=columnspan,
              sticky=sticky, padx=padx, pady=pady)
    card.grid_columnconfigure(0, weight=1)

    # Header strip — emoji + title + 2 px accent underline so each card
    # has a distinct identity without a full-width banner.
    head = ctk.CTkFrame(card, fg_color="transparent")
    head.grid(row=0, column=0, sticky="ew",
              padx=theme.PADDING_CARD, pady=(theme.PADDING_CARD, 4))
    head.grid_columnconfigure(1, weight=1)

    if emoji:
        img = emoji_for(emoji, emoji_size)
        if img is not None:
            ctk.CTkLabel(head, image=img, text="").grid(
                row=0, column=0, sticky="w",
                padx=(0, theme.S2),
            )

    ctk.CTkLabel(
        head, text=title, anchor="w",
        font=theme.FONT_SUBHEAD, text_color=accent,
    ).grid(row=0, column=1, sticky="ew")

    ctk.CTkFrame(
        card, fg_color=accent, height=2, corner_radius=1,
    ).grid(row=1, column=0, sticky="w",
           padx=theme.PADDING_CARD, pady=(0, 8))

    content = ctk.CTkFrame(card, fg_color="transparent")
    content.grid(row=2, column=0, sticky="nsew",
                 padx=theme.PADDING_CARD,
                 pady=(0, theme.PADDING_CARD))
    content.grid_columnconfigure(0, weight=1)
    card.grid_rowconfigure(2, weight=1)
    return content
