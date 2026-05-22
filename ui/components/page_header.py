"""Shared page header — emoji + title + optional subtitle + divider.

Caller passes an `emoji` char (e.g. "🏠") and the title; the header
renders the emoji as a color image (via Pillow) next to the title text.
Falls back to text-only if Pillow rasterization fails.

Returns nothing — the caller positions subsequent content starting at
`row + 2` (header at `row`, divider at `row+1`).
"""
from __future__ import annotations

import customtkinter as ctk

from ui import theme
from ui.emoji_image import emoji_for


def page_header(parent, *, title: str, subtitle: str = "",
                emoji: str = "", emoji_size: int = 28,
                row: int = 0, pady_top: int = 6,
                pady_bot: int = 16) -> None:
    head = ctk.CTkFrame(parent, fg_color="transparent")
    head.grid(row=row, column=0, sticky="ew", pady=(pady_top, 4))
    head.grid_columnconfigure(1, weight=1)

    if emoji:
        img = emoji_for(emoji, emoji_size)
        if img is not None:
            ctk.CTkLabel(head, image=img, text="").grid(
                row=0, column=0, rowspan=2, sticky="w",
                padx=(0, theme.S3),
            )

    ctk.CTkLabel(
        head, text=title, anchor="w",
        font=theme.FONT_HEADING, text_color=theme.TEXT,
    ).grid(row=0, column=1, sticky="ew")

    if subtitle:
        ctk.CTkLabel(
            head, text=subtitle, anchor="w",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=1, sticky="ew", pady=(2, 0))

    ctk.CTkFrame(
        parent, fg_color=theme.BORDER_DIM, height=1, corner_radius=0,
    ).grid(row=row + 1, column=0, sticky="ew", pady=(2, pady_bot))
