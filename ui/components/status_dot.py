"""Solid status dot — a rounded CTkFrame in the status color.

For indicators <= 18 px, prefer this over Pillow color emoji: small
emoji images suffer visible edge clipping no matter how careful the
rasterizer is. A solid square reads cleaner at small sizes.
"""
from __future__ import annotations

import customtkinter as ctk

from ui import theme


def status_dot(parent, *, color: str, size: int = 10) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        fg_color=color,
        width=size, height=size,
        corner_radius=max(2, size // 2),
    )


def dot_for(parent, status: str, *, size: int = 10) -> ctk.CTkFrame:
    """Map a pipeline phase status to the right colored dot.

    Accepted statuses: pending, running, done, error, stopped, warn.
    Unknown statuses fall back to TEXT_DIM.
    """
    color = {
        "pending": theme.TEXT_DIM,
        "running": theme.ACCENT,
        "done":    theme.ONLINE,
        "ok":      theme.ONLINE,
        "error":   theme.OFFLINE,
        "failed":  theme.OFFLINE,
        "stopped": theme.WARN,
        "warn":    theme.WARN,
        "info":    theme.INFO,
    }.get(status, theme.TEXT_DIM)
    return status_dot(parent, color=color, size=size)
