"""Borderless dark modal helper.

Windows' default title bar on `CTkToplevel` is white-on-white — clashes
with our dark theme. We strip it via `overrideredirect(True)` and paint
our own with theme colors. A drag-handler on the custom title bar lets
the user move the window like normal.

Usage:
    win, body = dark_modal(parent, title="Building .exe",
                            width=520, height=200)
    # populate `body` (a CTkFrame) with whatever content you want.

The function returns (toplevel, body_frame). Body is already gridded
inside `toplevel.content_frame`.
"""
from __future__ import annotations

from typing import Tuple

import customtkinter as ctk

from ui import theme
from ui.emoji_image import emoji_for


def dark_modal(parent, *, title: str, width: int = 480,
               height: int = 200, emoji: str = "",
               closable: bool = True) -> Tuple[ctk.CTkToplevel, ctk.CTkFrame]:
    """Create a borderless dark toplevel modal.

    Returns (window, body) — caller fills `body` with content.
    Caller is responsible for calling `window.destroy()` when done.
    """
    win = ctk.CTkToplevel(parent)
    # Strip the native title bar — we draw our own.
    win.overrideredirect(True)
    win.configure(fg_color=theme.BG_PAGE)
    win.geometry(f"{width}x{height}")
    win.transient(parent.winfo_toplevel())
    win.grab_set()

    # Center over the parent window.
    try:
        parent.winfo_toplevel().update_idletasks()
        px = parent.winfo_toplevel().winfo_rootx()
        py = parent.winfo_toplevel().winfo_rooty()
        pw = parent.winfo_toplevel().winfo_width()
        ph = parent.winfo_toplevel().winfo_height()
        x = px + max(0, (pw - width) // 2)
        y = py + max(0, (ph - height) // 3)
        win.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass

    # Container with a thin border so the modal reads as a "card."
    shell = ctk.CTkFrame(
        win, fg_color=theme.BG_PAGE,
        border_color=theme.BORDER, border_width=1,
        corner_radius=theme.RADIUS_CARD,
    )
    shell.pack(fill="both", expand=True)
    shell.grid_columnconfigure(0, weight=1)
    shell.grid_rowconfigure(1, weight=1)

    # ── Custom title bar ────────────────────────────────────────────────
    bar = ctk.CTkFrame(
        shell, fg_color=theme.BG_SIDEBAR, height=36, corner_radius=0,
    )
    bar.grid(row=0, column=0, sticky="ew")
    bar.grid_columnconfigure(1, weight=1)
    bar.grid_propagate(False)

    # Drag handler — move the window when user drags the title bar.
    drag = {"x": 0, "y": 0}

    def _press(e):
        drag["x"] = e.x_root - win.winfo_x()
        drag["y"] = e.y_root - win.winfo_y()

    def _motion(e):
        try:
            win.geometry(f"+{e.x_root - drag['x']}+{e.y_root - drag['y']}")
        except Exception:
            pass

    bar.bind("<Button-1>", _press)
    bar.bind("<B1-Motion>", _motion)

    if emoji:
        img = emoji_for(emoji, 16)
        if img is not None:
            lbl = ctk.CTkLabel(bar, image=img, text="")
            lbl.grid(row=0, column=0, padx=(theme.S3, theme.S2), pady=8)
            lbl.bind("<Button-1>", _press)
            lbl.bind("<B1-Motion>", _motion)

    title_lbl = ctk.CTkLabel(
        bar, text=title, anchor="w",
        font=theme.FONT_BODY_BOLD, text_color=theme.TEXT,
    )
    title_lbl.grid(row=0, column=1, sticky="ew", padx=theme.S2)
    title_lbl.bind("<Button-1>", _press)
    title_lbl.bind("<B1-Motion>", _motion)

    if closable:
        ctk.CTkButton(
            bar, text="X",
            fg_color="transparent",
            hover_color=theme.OFFLINE,
            text_color=theme.TEXT_SUB,
            font=theme.FONT_BODY_BOLD,
            width=36, height=28,
            corner_radius=theme.RADIUS_SMALL,
            command=lambda: (win.grab_release(), win.destroy()),
        ).grid(row=0, column=2, sticky="e", padx=theme.S2, pady=4)

    # ── Body ────────────────────────────────────────────────────────────
    body = ctk.CTkFrame(shell, fg_color=theme.BG_PAGE)
    body.grid(row=1, column=0, sticky="nsew",
              padx=theme.S4, pady=theme.S3)
    body.grid_columnconfigure(0, weight=1)

    # Hold ref so caller can re-use it.
    win.content_frame = body
    return win, body
