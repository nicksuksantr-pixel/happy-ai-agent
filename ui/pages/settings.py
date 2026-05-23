"""Settings — Auth + Model + Pipeline + Reset cards.

Each card uses `section_card` so the page reads as a stack of clearly-
named regions. Sliders + radios pick up the accent color. All labels
English.
"""
from __future__ import annotations

import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from auth import (
    clear_api_key,
    create_client,
    is_valid_key_format,
    list_available_models,
    save_api_key,
    test_connection,
)

from core import config
from ui import theme
from ui.components.clipboard import enable_clipboard_shortcuts
from ui.components.page_header import page_header
from ui.components.section_card import section_card
from ui.components.status_dot import status_dot


class SettingsPage(ctk.CTkFrame):
    PAGE_ID = "settings"

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app

        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.BORDER_DIM,
        )
        scroll.pack(fill="both", expand=True, padx=22, pady=18)
        scroll.grid_columnconfigure(0, weight=1)

        page_header(
            scroll, title="Settings",
            subtitle="Connect Gemini, pick a model, tune the pipeline.",
            emoji="⚙",
            row=0,
        )

        self._build_auth(scroll, row=10)
        self._build_model(scroll, row=11)
        self._build_pipeline(scroll, row=12)
        self._build_updates(scroll, row=13)
        self._build_reset(scroll, row=14)

    # ── Auth card ────────────────────────────────────────────────────────
    def _build_auth(self, parent, row: int) -> None:
        c = section_card(parent, title="Gemini connection",
                          accent=theme.ACCENT, emoji="🔐",
                          row=row, pady=(4, 10))

        # v2.4.8: edit-mode toggle. When a key is saved and the user
        # isn't actively replacing it, the input row + Save button are
        # hidden and a big "Saved key" card is shown instead — so the
        # field that used to look empty (and confused Nick into
        # thinking no key was stored) is replaced with an unambiguous
        # visual confirmation. Clicking "Change key" flips the toggle
        # and reveals the input + a Cancel button.
        self._editing_key: bool = False

        # Status row with dot (always visible) -----------------------------
        sr = ctk.CTkFrame(c, fg_color="transparent")
        sr.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        sr.grid_columnconfigure(1, weight=1)
        self._auth_dot = status_dot(sr, color=theme.OFFLINE, size=10)
        self._auth_dot.grid(row=0, column=0, padx=(0, 10))
        self.auth_status_label = ctk.CTkLabel(
            sr, text="Not connected.",
            font=theme.FONT_BODY, text_color=theme.TEXT_SUB, anchor="w",
        )
        self.auth_status_label.grid(row=0, column=1, sticky="ew")

        # ── ROW 1: "Saved key" card (visible only when connected + not editing)
        self.saved_key_card = ctk.CTkFrame(
            c, fg_color=theme.BG_INPUT,
            border_color=theme.ONLINE, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        self.saved_key_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self.saved_key_card, text="🔑",
            font=(theme.FAMILY, 18),
        ).grid(row=0, column=0, padx=(14, 10), pady=12, sticky="w")
        sk_text = ctk.CTkFrame(self.saved_key_card, fg_color="transparent")
        sk_text.grid(row=0, column=1, sticky="ew", pady=10)
        sk_text.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            sk_text, text="API KEY SAVED ON THIS MACHINE",
            font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        self.saved_key_label = ctk.CTkLabel(
            sk_text, text="",
            font=(theme.FAMILY_MONO, 13, "bold"),
            text_color=theme.ONLINE, anchor="w",
        )
        self.saved_key_label.grid(row=1, column=0, sticky="ew",
                                   pady=(2, 0))
        self.change_key_btn = ctk.CTkButton(
            self.saved_key_card, text="Change key",
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color="white",
            font=theme.FONT_BODY_BOLD,
            height=34, width=120,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._enter_edit_mode,
        )
        self.change_key_btn.grid(row=0, column=2, padx=(8, 12), pady=10)
        # Gridded-in on demand by _refresh_auth_status.

        # ── ROW 1 alt: hint label (visible when entering a key) ───────────
        # Same widget as v2.4.7; just promoted to the "edit-mode" slot.
        self.key_hint_label = ctk.CTkLabel(
            c, anchor="w", text_color=theme.TEXT_DIM,
            font=theme.FONT_TINY,
            text="Paste your API key below (starts with AIzaSy…)",
        )

        # ── ROW 2: input row (visible when not connected OR editing) ──────
        self.input_row = ctk.CTkFrame(c, fg_color="transparent")
        self.input_row.grid_columnconfigure(0, weight=1)
        self.api_key_input = ctk.CTkEntry(
            self.input_row,
            # No placeholder_text — its interaction with show="*"
            # used to wipe typed keys on re-focus (v2.4.3 bug).
            show="*",
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_DIM,
            text_color=theme.TEXT,
            font=theme.FONT_CODE,
            height=38,
        )
        self.api_key_input.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        # Thai-keyboard-safe Ctrl+V/C/X/A + right-click menu.
        enable_clipboard_shortcuts(self.api_key_input)
        ctk.CTkButton(
            self.input_row, text="Save & connect",
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color="white",
            font=theme.FONT_BODY_BOLD,
            height=38, width=150,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._save_api_key,
        ).grid(row=0, column=1, padx=(0, 6))
        # Cancel button — only visible while editing an existing key.
        self.cancel_change_btn = ctk.CTkButton(
            self.input_row, text="Cancel",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.TEXT_SUB,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BORDER,
            font=theme.FONT_BODY,
            height=38, width=90,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._exit_edit_mode,
        )
        # Gridded-in on demand.

        # ── ROW 3: "Get a free key" link (always) ─────────────────────────
        ctk.CTkButton(
            c, text="Get a free API key at AI Studio  ->",
            fg_color="transparent",
            text_color=theme.ACCENT,
            hover_color=theme.BG_CARD_HOVER, anchor="w",
            font=theme.FONT_SMALL,
            command=lambda: webbrowser.open(
                "https://aistudio.google.com/apikey"
            ),
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))

        # ── ROW 4: action row (always) ────────────────────────────────────
        ar = ctk.CTkFrame(c, fg_color="transparent")
        ar.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ar.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            ar, text="Test connection",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.TEXT,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BORDER,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._test_connection,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            ar, text="Log out (clear key)",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.OFFLINE,
            border_width=1, border_color=theme.BORDER,
            hover_color="#3a1f1f",
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._logout,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self._refresh_auth_status()

    # ── Model card ───────────────────────────────────────────────────────
    def _build_model(self, parent, row: int) -> None:
        c = section_card(parent, title="Model",
                          accent=theme.ACCENT_2, emoji="🤖",
                          row=row, pady=(0, 10))

        models = self.app.app_state.available_models or [
            "gemini-3.1-flash-lite-preview",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3.1-pro-preview",
            "gemini-2.5-pro",
        ]
        if self.app.app_state.model not in models:
            models = [self.app.app_state.model] + models

        self.model_var = ctk.StringVar(value=self.app.app_state.model)
        self.model_menu = ctk.CTkOptionMenu(
            c, values=models, variable=self.model_var,
            fg_color=theme.BG_INPUT,
            button_color=theme.ACCENT_2,
            button_hover_color=theme.ACCENT_2_HOVER,
            text_color=theme.TEXT,
            dropdown_fg_color=theme.BG_CARD,
            dropdown_text_color=theme.TEXT,
            dropdown_hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_BODY, height=36,
            command=self._on_model_change,
        )
        self.model_menu.grid(row=0, column=0, sticky="ew", pady=2)

        # Free-tier label updates live to the picked model — no more
        # claiming RPD 500 while the user has gemini-2.5-pro selected
        # (real cap there is 100/day).
        self._model_quota_label = ctk.CTkLabel(
            c, anchor="w", text_color=theme.TEXT_DIM,
            font=theme.FONT_TINY,
            text=self._build_model_quota_text(self.app.app_state.model),
        )
        self._model_quota_label.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        r = ctk.CTkFrame(c, fg_color="transparent")
        r.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        r.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            r, text="Refresh model list",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.TEXT,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BORDER,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._refresh_models,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            r, text="Test current model",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.TEXT,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BORDER,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._test_model,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

    # ── Pipeline card ────────────────────────────────────────────────────
    def _build_pipeline(self, parent, row: int) -> None:
        c = section_card(parent, title="Pipeline tuning",
                          accent=theme.ACCENT_4, emoji="⚡",
                          row=row, pady=(0, 10))

        ctk.CTkLabel(
            c, text="Mode", anchor="w",
            font=theme.FONT_LABEL, text_color=theme.TEXT,
        ).grid(row=0, column=0, sticky="w")
        self.mode_var = ctk.StringVar(value=self.app.app_state.pipeline_mode)
        mr = ctk.CTkFrame(c, fg_color="transparent")
        mr.grid(row=1, column=0, sticky="ew", pady=(2, 14))
        mr.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkRadioButton(
            mr, text="Quick   (11 phases, ~10 min)",
            variable=self.mode_var, value="quick",
            fg_color=theme.ACCENT, border_color=theme.BORDER,
            text_color=theme.TEXT, hover_color=theme.ACCENT_HOVER,
            font=theme.FONT_BODY, command=self._on_mode_change,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkRadioButton(
            mr, text="Thorough  (18 phases, ~20 min)",
            variable=self.mode_var, value="thorough",
            fg_color=theme.ACCENT, border_color=theme.BORDER,
            text_color=theme.TEXT, hover_color=theme.ACCENT_HOVER,
            font=theme.FONT_BODY, command=self._on_mode_change,
        ).grid(row=0, column=1, sticky="w")

        # Delay
        self.delay_label = ctk.CTkLabel(
            c, anchor="w", text_color=theme.TEXT_SUB,
            font=theme.FONT_BODY,
            text=f"Phase delay: {self.app.app_state.delay}s",
        )
        self.delay_label.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        # v2.4.7: min lowered 30→5s per Nick. Power users on paid
        # tier (or testing) want to burn through phases quickly.
        # Step is 5 seconds: 5/10/15/.../180.
        self.delay_slider = ctk.CTkSlider(
            c, from_=5, to=180, number_of_steps=35,
            command=self._on_delay_change,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
            progress_color=theme.ACCENT,
            fg_color=theme.BG_INPUT,
        )
        self.delay_slider.set(self.app.app_state.delay)
        self.delay_slider.grid(row=3, column=0, sticky="ew", pady=(2, 0))
        ctk.CTkLabel(
            c, text="Recommended: 45s on free tier · 5–15s on paid tier",
            anchor="w", text_color=theme.TEXT_DIM, font=theme.FONT_TINY,
        ).grid(row=4, column=0, sticky="w", pady=(2, 8))

        # Judge threshold
        self.judge_label = ctk.CTkLabel(
            c, anchor="w", text_color=theme.TEXT_SUB,
            font=theme.FONT_BODY,
            text=f"Judge minimum: {self.app.app_state.judge_threshold}/100",
        )
        self.judge_label.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self.judge_slider = ctk.CTkSlider(
            c, from_=50, to=100, number_of_steps=10,
            command=self._on_judge_change,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
            progress_color=theme.ACCENT,
            fg_color=theme.BG_INPUT,
        )
        self.judge_slider.set(self.app.app_state.judge_threshold)
        self.judge_slider.grid(row=6, column=0, sticky="ew", pady=(2, 0))

        # Loops
        self.loops_label = ctk.CTkLabel(
            c, anchor="w", text_color=theme.TEXT_SUB,
            font=theme.FONT_BODY,
            text=f"Max revision loops: {self.app.app_state.max_judge_loops}",
        )
        self.loops_label.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        self.loops_slider = ctk.CTkSlider(
            c, from_=1, to=10, number_of_steps=9,
            command=self._on_loops_change,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
            progress_color=theme.ACCENT,
            fg_color=theme.BG_INPUT,
        )
        self.loops_slider.set(self.app.app_state.max_judge_loops)
        self.loops_slider.grid(row=8, column=0, sticky="ew", pady=(2, 0))

    # ── Updates card ─────────────────────────────────────────────────────
    def _build_updates(self, parent, row: int) -> None:
        c = section_card(parent, title="Updates",
                          accent=theme.SUCCESS, emoji="⬇",
                          row=row, pady=(0, 10))

        self.update_status_label = ctk.CTkLabel(
            c, text=f"Current version: v{config.VERSION}",
            font=theme.FONT_BODY, text_color=theme.TEXT_SUB,
            anchor="w",
        )
        self.update_status_label.grid(row=0, column=0, sticky="ew",
                                       pady=(0, theme.S2))

        self.update_btn = ctk.CTkButton(
            c, text="Check for updates",
            fg_color=theme.SUCCESS, hover_color="#16a34a",
            text_color="white",
            font=theme.FONT_BODY_BOLD, height=36,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._check_updates,
        )
        self.update_btn.grid(row=1, column=0, sticky="ew")

        ctk.CTkLabel(
            c, text=f"Auto-checks every hour. Releases at: "
                    f"github.com/nicksuksantr-pixel/happy-ai-agent",
            font=theme.FONT_TINY, text_color=theme.TEXT_DIM,
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", pady=(theme.S2, 0))

    def _check_updates(self) -> None:
        """Fire a one-shot update check + report result inline."""
        import threading as _th
        import updater as _up
        self.update_btn.configure(state="disabled", text="Checking...")
        self.update_status_label.configure(
            text="Reaching GitHub...",
            text_color=theme.TEXT_SUB,
        )

        def worker():
            try:
                info = _up.check_for_update(config.VERSION, timeout=6.0)
            except Exception:
                info = None
            self.after(0, lambda i=info: self._on_check_done(i))

        _th.Thread(target=worker, daemon=True).start()

    def _on_check_done(self, info) -> None:
        self.update_btn.configure(state="normal", text="Check for updates")
        if info is None:
            self.update_status_label.configure(
                text=f"You're on v{config.VERSION} — already up to date.",
                text_color=theme.ONLINE,
            )
            return
        # Forward the discovery to the app so the sidebar pill + install
        # offer come up.
        self.update_status_label.configure(
            text=f"Update available: v{info.version} (you're on v{config.VERSION})",
            text_color=theme.ACCENT,
        )
        try:
            self.app._on_update_found(info)
        except Exception:
            pass

    # ── Reset card ───────────────────────────────────────────────────────
    def _build_reset(self, parent, row: int) -> None:
        c = section_card(parent, title="Reset",
                          accent=theme.ACCENT_3, emoji="🔄",
                          row=row, pady=(0, 20))
        ctk.CTkButton(
            c, text="Reset all settings to defaults",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.TEXT,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BORDER,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._reset_settings,
        ).grid(row=0, column=0, sticky="ew")

    # ── Auth handlers ────────────────────────────────────────────────────
    def _refresh_auth_status(self) -> None:
        """Update the status row text + swap auth-card layout between
        "saved-key card" (connected + not editing) and "input row"
        (disconnected OR editing).
        """
        s = self.app.app_state
        is_connected = s.auth_ready
        is_editing = getattr(self, "_editing_key", False)

        # ── Status row (always) ───────────────────────────────────────
        if is_connected:
            k = s.api_key
            masked = f"{k[:6]}...{k[-4:]}" if len(k) > 12 else "***"
            self.auth_status_label.configure(
                text=f"Connected — key {masked}",
                text_color=theme.ONLINE,
            )
            self._auth_dot.configure(fg_color=theme.ONLINE)
            # Also populate the big card label (only visible when
            # `saved_key_card` is gridded in below).
            try:
                self.saved_key_label.configure(text=masked)
            except Exception:
                pass
        else:
            self.auth_status_label.configure(
                text="Not connected. Paste an API key below.",
                text_color=theme.TEXT_SUB,
            )
            self._auth_dot.configure(fg_color=theme.OFFLINE)

        # ── Layout swap ───────────────────────────────────────────────
        # State A: connected + NOT editing  →  show big "Saved key" card,
        #                                        hide hint + input row
        # State B: disconnected OR editing  →  show hint + input row,
        #                                        hide saved-key card
        if is_connected and not is_editing:
            try:
                self.saved_key_card.grid(
                    row=1, column=0, sticky="ew", pady=(0, 6)
                )
                self.key_hint_label.grid_remove()
                self.input_row.grid_remove()
                self.cancel_change_btn.grid_remove()
            except Exception:
                pass
        else:
            try:
                self.saved_key_card.grid_remove()
                # Hint text differs depending on whether we're entering
                # a first-time key or replacing one.
                if is_editing and is_connected:
                    k = s.api_key
                    m = f"{k[:6]}...{k[-4:]}" if len(k) > 12 else "***"
                    self.key_hint_label.configure(
                        text=f"Paste a NEW key to replace {m}  "
                             f"·  click Cancel to keep the current one"
                    )
                else:
                    self.key_hint_label.configure(
                        text="Paste your API key below (starts with AIzaSy…)"
                    )
                self.key_hint_label.grid(
                    row=1, column=0, sticky="w", pady=(0, 4)
                )
                self.input_row.grid(
                    row=2, column=0, sticky="ew", pady=2
                )
                # Cancel button: only shown when leaving edit-mode
                # without saving makes sense — i.e. user already has a
                # connected key AND is mid-edit. For a fresh sign-in
                # (not connected, not editing) there's nothing to
                # cancel back to. The `is_connected` guard prevents the
                # button from appearing in the impossible-but-defensive
                # disconnected+editing state.
                if is_editing and is_connected:
                    self.cancel_change_btn.grid(
                        row=0, column=2, padx=(0, 0)
                    )
                else:
                    self.cancel_change_btn.grid_remove()
            except Exception:
                pass

    def _enter_edit_mode(self) -> None:
        """Flip the auth card into "paste a new key" mode + focus the
        input. Triggered by the Change-key button on the saved-key card."""
        self._editing_key = True
        try:
            self.api_key_input.delete(0, "end")
        except Exception:
            pass
        self._refresh_auth_status()
        try:
            self.api_key_input.focus_set()
        except Exception:
            pass

    def _exit_edit_mode(self) -> None:
        """Cancel an in-progress key change. Discards whatever was
        typed and returns to the saved-key card view."""
        self._editing_key = False
        try:
            self.api_key_input.delete(0, "end")
        except Exception:
            pass
        self._refresh_auth_status()

    def _save_api_key(self) -> None:
        key = self.api_key_input.get().strip()
        if not key:
            messagebox.showwarning("Missing key", "Paste an API key first.")
            return
        if not is_valid_key_format(key):
            messagebox.showerror(
                "Bad format",
                "API key must start with 'AIza' and be at least 35 chars.",
            )
            return
        client, err = create_client(key)
        if err:
            messagebox.showerror("Client error", err)
            return
        ok, _ = test_connection(client)
        if not ok:
            messagebox.showerror(
                "Connection failed",
                "Could not reach Gemini with that key. "
                "Verify the key at aistudio.google.com/apikey and retry.",
            )
            return
        save_api_key(key)
        self.app.app_state.client = client
        self.app.app_state.api_key = key
        self.app.app_state.auth_ready = True
        try:
            models = list_available_models(client) or []
            self.app.app_state.available_models = models
            if models and self.app.app_state.model not in models:
                self.app.app_state.model = models[0]
                self.model_var.set(models[0])
            if models:
                self.model_menu.configure(values=models)
        except Exception:
            pass
        self.app.app_state.persist()
        # Successful save: clear input + exit edit mode so the big
        # "Saved key" card replaces the input row.
        self._editing_key = False
        self.api_key_input.delete(0, "end")
        self._refresh_auth_status()
        self.app.sidebar.refresh_auth_status()
        messagebox.showinfo(
            "Connected",
            "Saved. Happy AI Agent will auto-login next time.",
        )

    def _test_connection(self) -> None:
        # In edit mode with typed input → test the TYPED key (what the
        # user is about to save). Otherwise → test the saved client.
        # Without this branch, Test silently verifies the OLD key while
        # the user thinks they're checking the new one they just typed,
        # which produces the confusing "Test passed but my new key was
        # never actually verified" footgun.
        typed = ""
        if getattr(self, "_editing_key", False):
            try:
                typed = self.api_key_input.get().strip()
            except Exception:
                typed = ""

        if typed:
            if not is_valid_key_format(typed):
                messagebox.showerror(
                    "Bad format",
                    "Type a valid API key first "
                    "(starts with AIza, >=35 chars).",
                )
                return
            client, err = create_client(typed)
            if err:
                messagebox.showerror("Client error", err)
                return
            ok, _ = test_connection(client)
        else:
            if not self.app.app_state.client:
                messagebox.showwarning(
                    "Not connected", "Save an API key first."
                )
                return
            ok, _ = test_connection(self.app.app_state.client)

        if ok:
            messagebox.showinfo(
                "Test passed", "Gemini responded successfully.",
            )
        else:
            messagebox.showerror(
                "Test failed",
                "Could not reach Gemini. Check the key and network.",
            )

    def _logout(self) -> None:
        if not messagebox.askyesno(
            "Log out?",
            "Remove the saved API key from this machine?",
        ):
            return
        clear_api_key()
        self.app.app_state.client = None
        self.app.app_state.api_key = ""
        self.app.app_state.auth_ready = False
        self.app.app_state.available_models = []
        # After logout the input row should re-appear (not the saved-
        # key card). Edit mode flag doesn't matter once auth_ready is
        # False, but reset it for cleanliness.
        self._editing_key = False
        self._refresh_auth_status()
        self.app.sidebar.refresh_auth_status()

    # ── Model handlers ───────────────────────────────────────────────────
    def _build_model_quota_text(self, model: str) -> str:
        """One-liner shown under the model dropdown — picks numbers from
        core.quotas so the text matches the (best-known) free-tier limit
        for whatever model is selected.

        v2.5.0: numbers are framed as ESTIMATES with a "~" prefix. The
        static table in core.quotas is best-effort — Google rotates
        free-tier ceilings silently and Nick caught us claiming
        "RPD cap 1000/day" for gemini-3.1-flash-lite when nobody on
        the team had actually verified that number with Google."""
        from core.quotas import get_quota
        q = get_quota(model)
        return (f"{model or '(none)'}  ·  free tier est: "
                f"~RPM {q.rpm}  ·  ~TPM {q.tpm:,}  ·  ~RPD {q.rpd}/day  "
                f"·  verify at ai.google.dev")

    def _on_model_change(self, value: str) -> None:
        self.app.app_state.model = value
        self.app.app_state.persist()
        # Refresh the quota hint so it reflects the new model's limits.
        try:
            self._model_quota_label.configure(
                text=self._build_model_quota_text(value)
            )
        except Exception:
            pass

    def _refresh_models(self) -> None:
        if not self.app.app_state.client:
            messagebox.showwarning("Not connected", "Connect first.")
            return
        try:
            models = list_available_models(self.app.app_state.client) or []
            self.app.app_state.available_models = models
            self.model_menu.configure(
                values=models or [self.app.app_state.model]
            )
            messagebox.showinfo(
                "Model list refreshed",
                f"Found {len(models)} models.",
            )
        except Exception as e:
            messagebox.showerror("Refresh failed", str(e)[:200])

    def _test_model(self) -> None:
        if not self.app.app_state.client:
            messagebox.showwarning("Not connected", "Connect first.")
            return
        try:
            r = self.app.app_state.client.models.generate_content(
                model=self.app.app_state.model,
                contents=(
                    "Reply in one short English sentence confirming "
                    "you are Gemini and ready for work."
                ),
            )
            reply = (r.text or "").strip()[:300] or "(empty)"
            messagebox.showinfo(
                "Model test passed",
                f"{self.app.app_state.model} is ready.\n\nReply: {reply}",
            )
        except Exception as e:
            messagebox.showerror("Model test failed", str(e)[:300])

    # ── Pipeline handlers ────────────────────────────────────────────────
    def _on_mode_change(self) -> None:
        self.app.app_state.pipeline_mode = self.mode_var.get()
        self.app.app_state.persist()

    def _on_delay_change(self, value) -> None:
        v = int(round(value))
        self.app.app_state.delay = v
        self.delay_label.configure(text=f"Phase delay: {v}s")
        self.app.app_state.persist()

    def _on_judge_change(self, value) -> None:
        v = int(round(value))
        self.app.app_state.judge_threshold = v
        self.judge_label.configure(text=f"Judge minimum: {v}/100")
        self.app.app_state.persist()

    def _on_loops_change(self, value) -> None:
        v = int(round(value))
        self.app.app_state.max_judge_loops = v
        self.loops_label.configure(text=f"Max revision loops: {v}")
        self.app.app_state.persist()

    # ── Reset handler ────────────────────────────────────────────────────
    def _reset_settings(self) -> None:
        if not messagebox.askyesno(
            "Reset?", "Reset all settings to defaults?"
        ):
            return
        for k, v in config.DEFAULT_SETTINGS.items():
            setattr(self.app.app_state, k, v)
        self.app.app_state.persist()
        self.model_var.set(self.app.app_state.model)
        self.mode_var.set(self.app.app_state.pipeline_mode)
        self.delay_slider.set(self.app.app_state.delay)
        self.judge_slider.set(self.app.app_state.judge_threshold)
        self.loops_slider.set(self.app.app_state.max_judge_loops)
        self.delay_label.configure(
            text=f"Phase delay: {self.app.app_state.delay}s"
        )
        self.judge_label.configure(
            text=f"Judge minimum: {self.app.app_state.judge_threshold}/100"
        )
        self.loops_label.configure(
            text=f"Max revision loops: {self.app.app_state.max_judge_loops}"
        )

    def on_show(self) -> None:
        self._refresh_auth_status()
