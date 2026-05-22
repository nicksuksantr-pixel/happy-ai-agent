"""Left sidebar — logo, lean nav (4 routes), auth + update pills.

v2.2.0 stripped the fake "runs today / rpd ceiling" stats and the
duplicate Recent Runs list (history now lives on the dedicated Runs
page). Sidebar = navigation + status only.

Active nav route gets a 3-px accent strip on the left edge + a lifted
background + accent text. Idle nav rows are transparent (no garish
border on startup per the no-idle-highlight rule).
"""
from __future__ import annotations

from typing import Dict, Tuple

import customtkinter as ctk

from core import config
from ui import theme
from ui.components.logo import load_logo_image
from ui.components.status_dot import status_dot
from ui.emoji_image import emoji_for


_NAV_SPEC: list[Tuple[str, str, str]] = [
    # (page_id, emoji char, label)
    ("home",     "🏠", "Home"),
    ("runs",     "📋", "Runs"),
    ("stats",    "📊", "Stats"),
    ("settings", "⚙",  "Settings"),
]


class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(
            parent,
            width=config.SIDEBAR_W,
            fg_color=theme.BG_SIDEBAR,
            border_width=0,
            corner_radius=0,
        )
        self.app = app
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        # Row 4 (nav scrollable spacer) takes the slack so the bottom
        # status pills hug the bottom edge.
        self.grid_rowconfigure(4, weight=1)

        # ── Logo block ──────────────────────────────────────────────────
        logo_box = ctk.CTkFrame(self, fg_color="transparent")
        logo_box.grid(row=0, column=0, sticky="ew",
                      padx=theme.S4, pady=(theme.S5, theme.S3))
        logo_box.grid_columnconfigure(0, weight=1)

        self._logo_img = load_logo_image(target_width=156)
        if self._logo_img is not None:
            ctk.CTkLabel(logo_box, image=self._logo_img, text="").grid(
                row=0, column=0, sticky="w"
            )
        else:
            ctk.CTkLabel(
                logo_box, text="HAPPY",
                font=theme.FONT_TITLE, text_color=theme.ACCENT, anchor="w",
            ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            logo_box, text="AI AGENT",
            font=theme.FONT_OVERLINE,
            text_color=theme.TEXT_DIM, anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(theme.S1, 0))

        # ── New Run CTA — first thing under the logo ────────────────────
        # Sparkle emoji as a hint that this is the "magic" button. Falls
        # back to a plain "+" if Pillow can't render color emoji.
        sparkle = emoji_for("✨", 18)
        new_run_btn = ctk.CTkButton(
            self, text="  New Run" if sparkle else "+   New Run",
            image=sparkle, compound="left",
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color="white",
            font=theme.FONT_BODY_BOLD, height=40,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._open_new_run,
        )
        new_run_btn.grid(row=1, column=0, sticky="ew",
                         padx=theme.S4, pady=(0, theme.S4))

        # ── Nav rows ────────────────────────────────────────────────────
        # Pack — not grid — so 4 nav rows stack TIGHTLY at the top even
        # when the surrounding grid layout has elastic rows. With grid +
        # no explicit row weights the rows ended up sharing the sidebar
        # height equally (~230 px gaps). Pack guarantees natural-height
        # stacking from the top down.
        self._nav_buttons: Dict[str, Tuple[ctk.CTkButton, ctk.CTkFrame]] = {}
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=2, column=0, sticky="ew", padx=theme.S2)
        for page_id, icon, label in _NAV_SPEC:
            self._add_nav(nav, page_id=page_id, icon=icon, label=label)

        # ── (row 4 is the elastic spacer) ──────────────────────────────

        # ── Bottom: divider + update pill + auth pill + version ─────────
        ctk.CTkFrame(
            self, fg_color=theme.BORDER_DIM, height=1, corner_radius=0,
        ).grid(row=5, column=0, sticky="ew",
               padx=theme.S4, pady=(theme.S3, theme.S2))

        # Update pill (hidden until updater finds a new release).
        self.update_pill = ctk.CTkButton(
            self,
            text="",
            font=theme.FONT_TINY,
            fg_color=theme.SUCCESS, hover_color="#16a34a",
            text_color="white",
            corner_radius=theme.RADIUS_SMALL,
            height=30,
            command=lambda: self.app.offer_install_update(),
        )

        # Auth pill — single line, dot + masked key.
        self.auth_pill = ctk.CTkFrame(
            self, fg_color=theme.BG_CARD,
            corner_radius=theme.RADIUS_SMALL,
        )
        self.auth_pill.grid(row=7, column=0, padx=theme.S3,
                            pady=(0, theme.S2), sticky="ew")
        self.auth_pill.grid_columnconfigure(1, weight=1)
        self._auth_dot = status_dot(
            self.auth_pill, color=theme.OFFLINE, size=10
        )
        self._auth_dot.grid(row=0, column=0, padx=(theme.S3, theme.S2),
                            pady=theme.S2)
        self.auth_label = ctk.CTkLabel(
            self.auth_pill, text="Not connected",
            font=theme.FONT_TINY, text_color=theme.TEXT_SUB,
            anchor="w", wraplength=160, justify="left",
        )
        self.auth_label.grid(row=0, column=1, sticky="ew",
                             padx=(0, theme.S3), pady=theme.S2)

        # Version footer.
        ctk.CTkLabel(
            self, text=f"v{config.VERSION}",
            font=theme.FONT_TINY, text_color=theme.TEXT_DIM, anchor="w",
        ).grid(row=8, column=0, padx=theme.S4 + theme.S1,
               pady=(theme.S1, theme.S3), sticky="w")

        self.refresh_auth_status()

    # ── Nav helpers ──────────────────────────────────────────────────────
    def _add_nav(self, parent, *, page_id: str, icon: str, label: str) -> None:
        # Active strip + button live in the same row frame so showing /
        # hiding the strip doesn't change the button's width.
        row_frame = ctk.CTkFrame(parent, fg_color="transparent", height=44)
        row_frame.pack(fill="x", pady=2)
        row_frame.pack_propagate(False)

        strip = ctk.CTkFrame(
            row_frame, fg_color="transparent",
            width=3, corner_radius=0,
        )
        strip.pack(side="left", fill="y", padx=(0, theme.S2))

        # Try real color emoji first; fall back to text rendering.
        emoji_img = emoji_for(icon, 18)
        btn = ctk.CTkButton(
            row_frame,
            text=f"   {label}" if emoji_img else f"  {icon}   {label}",
            image=emoji_img, compound="left",
            anchor="w", height=40,
            fg_color="transparent",
            text_color=theme.TEXT,
            hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_BODY_BOLD,
            corner_radius=theme.RADIUS_BUTTON,
            command=lambda pid=page_id: self.app.show_page(pid),
        )
        btn.pack(side="left", fill="both", expand=True)
        self._nav_buttons[page_id] = (btn, strip)

    def _mark_active(self, page_id: str) -> None:
        for pid, (btn, strip) in self._nav_buttons.items():
            if pid == page_id:
                btn.configure(
                    fg_color=theme.ACTIVE_NAV_BG,
                    text_color=theme.ACTIVE_NAV_TEXT,
                )
                strip.configure(fg_color=theme.ACCENT)
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=theme.TEXT,
                )
                strip.configure(fg_color="transparent")

    def _open_new_run(self) -> None:
        # Clear pipeline state + go Home + focus the textbox.
        self.app.app_state.current_session_path = None
        self.app.app_state.current_outputs = {}
        self.app.app_state.current_status = {}
        self.app.app_state.current_judge_rounds = []
        self.app.app_state.selected_agent = None
        self.app.show_page("home")
        try:
            home = self.app.pages.get("home")
            if home and hasattr(home, "focus_task"):
                home.focus_task()
        except Exception:
            pass

    # ── Update pill ──────────────────────────────────────────────────────
    def show_update_pill(self, info, *, state: str = "ready") -> None:
        """Show the sidebar update pill.

        state values:
          - "downloading" — yellow, downloading silently in background
          - "ready"       — green, downloaded, click to install
          - "queued"      — orange, pipeline is running so install deferred
        """
        try:
            colors = {
                "downloading": (theme.WARN, "#d97706",
                                f"Downloading v{info.version}..."),
                "ready":       (theme.SUCCESS, "#16a34a",
                                f"Update v{info.version} ready ->"),
                "queued":      (theme.ACCENT, theme.ACCENT_HOVER,
                                f"Update v{info.version} after run"),
            }
            fg, hover, text = colors.get(state, colors["ready"])
            self.update_pill.configure(
                text=text, fg_color=fg, hover_color=hover,
            )
            self.update_pill.grid(row=6, column=0, padx=theme.S3,
                                  pady=(0, theme.S2), sticky="ew")
        except Exception:
            pass

    def hide_update_pill(self) -> None:
        try:
            self.update_pill.grid_remove()
        except Exception:
            pass

    # ── Refresh hooks ────────────────────────────────────────────────────
    def refresh_auth_status(self) -> None:
        s = self.app.app_state
        self._mark_active(self.app.current_page)
        if s.auth_ready:
            k = s.api_key
            masked = f"{k[:6]}...{k[-4:]}" if len(k) > 12 else "***"
            self.auth_label.configure(
                text=f"Connected   {masked}",
                text_color=theme.ONLINE,
            )
            self._auth_dot.configure(fg_color=theme.ONLINE)
        else:
            self.auth_label.configure(
                text="Not connected",
                text_color=theme.TEXT_SUB,
            )
            self._auth_dot.configure(fg_color=theme.OFFLINE)

    def refresh_history(self) -> None:
        # Kept as a no-op so HappyApp.show_page can call it without a
        # branch. History UI now lives on the Runs page.
        return
