"""Stats — usage + trend metrics computed from real session data."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import customtkinter as ctk

from pipeline import list_sessions

from core import config
from ui import theme
from ui.emoji_image import emoji_for


class StatsPage(ctk.CTkFrame):
    PAGE_ID = "stats"

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app

        # Scrollable surface for small viewports.
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.BORDER_DIM,
        )
        scroll.pack(fill="both", expand=True,
                    padx=theme.PADDING_PAGE, pady=theme.PADDING_PAGE)
        scroll.grid_columnconfigure(0, weight=1)

        # ── Header (emoji + title + subtitle + Refresh button) ──────────
        head = ctk.CTkFrame(scroll, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        head.grid_columnconfigure(1, weight=1)

        stats_emoji = emoji_for("📊", 28)
        if stats_emoji is not None:
            ctk.CTkLabel(head, image=stats_emoji, text="").grid(
                row=0, column=0, rowspan=2, sticky="w",
                padx=(0, theme.S3),
            )

        ctk.CTkLabel(
            head, text="Stats", anchor="w",
            font=theme.FONT_HEADING, text_color=theme.TEXT,
        ).grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(
            head, text="Usage and trends, computed from your local runs.",
            anchor="w", font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=1, sticky="ew", pady=(theme.S1, 0))

        ctk.CTkButton(
            head, text="Refresh",
            fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_SUB,
            border_width=1, border_color=theme.BORDER,
            font=theme.FONT_BODY, height=32, width=90,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._refresh,
        ).grid(row=0, column=2, rowspan=2,
               sticky="e", padx=(theme.S3, 0))

        ctk.CTkFrame(
            scroll, fg_color=theme.BORDER_DIM, height=1, corner_radius=0,
        ).grid(row=1, column=0, sticky="ew",
               pady=(theme.S3, theme.S4))

        # ── Big numbers row (4 stat tiles) ──────────────────────────────
        tiles = ctk.CTkFrame(scroll, fg_color="transparent")
        tiles.grid(row=2, column=0, sticky="ew", pady=(0, theme.S4))
        tiles.grid_columnconfigure((0, 1, 2, 3), weight=1,
                                    uniform="tile")

        self._tile_total = self._build_tile(
            tiles, column=0, label="TOTAL RUNS",
            accent=theme.ACCENT,
        )
        self._tile_today = self._build_tile(
            tiles, column=1, label="TODAY",
            accent=theme.ACCENT_2,
        )
        self._tile_success = self._build_tile(
            tiles, column=2, label="SUCCESS RATE",
            accent=theme.ONLINE,
        )
        self._tile_avg = self._build_tile(
            tiles, column=3, label="AVG DURATION",
            accent=theme.ACCENT_3,
        )

        # ── Quota usage card ────────────────────────────────────────────
        self._quota_card = self._build_card(
            scroll, row=3, title="GEMINI QUOTA TODAY",
            accent=theme.ACCENT_3,
        )
        self._quota_label = ctk.CTkLabel(
            self._quota_card, text="",
            font=theme.FONT_BODY, text_color=theme.TEXT_SUB,
            anchor="w",
        )
        self._quota_label.grid(row=0, column=0, sticky="ew")
        self._quota_bar = ctk.CTkProgressBar(
            self._quota_card,
            progress_color=theme.ACCENT_3,
            fg_color=theme.BG_INPUT, height=8, corner_radius=4,
        )
        self._quota_bar.set(0)
        self._quota_bar.grid(row=1, column=0, sticky="ew",
                              pady=(theme.S2, theme.S1))
        self._quota_caption = ctk.CTkLabel(
            self._quota_card, text="",
            font=theme.FONT_TINY, text_color=theme.TEXT_DIM,
            anchor="w",
        )
        self._quota_caption.grid(row=2, column=0, sticky="ew")

        # ── Mode split card ─────────────────────────────────────────────
        self._mode_card = self._build_card(
            scroll, row=4, title="MODE SPLIT",
            accent=theme.ACCENT,
        )
        self._mode_quick_label = ctk.CTkLabel(
            self._mode_card, text="Quick   0",
            font=theme.FONT_BODY, text_color=theme.TEXT_SUB,
            anchor="w",
        )
        self._mode_quick_label.grid(row=0, column=0, sticky="ew",
                                     pady=(0, theme.S1))
        self._mode_quick_bar = ctk.CTkProgressBar(
            self._mode_card,
            progress_color=theme.ACCENT,
            fg_color=theme.BG_INPUT, height=6, corner_radius=3,
        )
        self._mode_quick_bar.set(0)
        self._mode_quick_bar.grid(row=1, column=0, sticky="ew")

        self._mode_thorough_label = ctk.CTkLabel(
            self._mode_card, text="Thorough   0",
            font=theme.FONT_BODY, text_color=theme.TEXT_SUB,
            anchor="w",
        )
        self._mode_thorough_label.grid(row=2, column=0, sticky="ew",
                                        pady=(theme.S3, theme.S1))
        self._mode_thorough_bar = ctk.CTkProgressBar(
            self._mode_card,
            progress_color=theme.ACCENT_2,
            fg_color=theme.BG_INPUT, height=6, corner_radius=3,
        )
        self._mode_thorough_bar.set(0)
        self._mode_thorough_bar.grid(row=3, column=0, sticky="ew")

        # ── Last 7 days card ────────────────────────────────────────────
        self._week_card = self._build_card(
            scroll, row=5, title="LAST 7 DAYS",
            accent=theme.ACCENT_2,
        )
        self._week_card.grid_columnconfigure(0, weight=1)
        # Row widgets created on each refresh.

    # ── Layout helpers ───────────────────────────────────────────────────
    def _build_tile(self, parent, *, column: int, label: str,
                    accent: str) -> ctk.CTkLabel:
        """Big-number stat tile. Returns the value label so refresh can
        update its text."""
        tile = ctk.CTkFrame(
            parent, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        tile.grid(row=0, column=column, sticky="nsew",
                  padx=(0 if column == 0 else theme.S2,
                        theme.S2 if column < 3 else 0))
        tile.grid_columnconfigure(0, weight=1)

        # Accent underline
        ctk.CTkFrame(
            tile, fg_color=accent, height=2, corner_radius=1,
        ).grid(row=0, column=0, sticky="ew",
               padx=theme.PADDING_CARD,
               pady=(theme.PADDING_CARD, theme.S1))

        value_lbl = ctk.CTkLabel(
            tile, text="—", anchor="w",
            font=theme.FONT_HERO_NUMBER, text_color=theme.TEXT,
        )
        value_lbl.grid(row=1, column=0, sticky="ew",
                       padx=theme.PADDING_CARD)

        ctk.CTkLabel(
            tile, text=label, anchor="w",
            font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
        ).grid(row=2, column=0, sticky="ew",
               padx=theme.PADDING_CARD,
               pady=(0, theme.PADDING_CARD))

        return value_lbl

    def _build_card(self, parent, *, row: int, title: str,
                    accent: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        card.grid(row=row, column=0, sticky="ew", pady=(0, theme.S4))
        card.grid_columnconfigure(0, weight=1)

        # Title bar with accent underline.
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew",
                  padx=theme.PADDING_CARD,
                  pady=(theme.PADDING_CARD, theme.S1))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head, text=title,
            font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkFrame(
            card, fg_color=accent, height=2, corner_radius=1,
        ).grid(row=1, column=0, sticky="w", padx=theme.PADDING_CARD,
               pady=(0, theme.S3))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew",
                     padx=theme.PADDING_CARD,
                     pady=(0, theme.PADDING_CARD))
        content.grid_columnconfigure(0, weight=1)
        return content

    # ── Lifecycle ────────────────────────────────────────────────────────
    def on_show(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        try:
            sessions = list_sessions()
        except Exception:
            sessions = []

        # Annotate sessions with their meta + parsed dates for reuse.
        rows = []
        for s in sessions:
            try:
                meta = json.loads(
                    (s["path"] / "_meta.json").read_text(encoding="utf-8")
                )
            except Exception:
                meta = {}
            rows.append((s, meta))

        total = len(rows)
        today = datetime.now().date()
        today_count = sum(
            1 for _, m in rows if self._row_date(m) == today
        )

        # Success rate: completed / (completed + stopped + failed). Running
        # sessions are excluded — they haven't decided yet.
        decided = [s for s, _ in rows
                   if s["status"] in ("completed", "stopped", "failed")]
        success_rate = (
            100 * sum(1 for s in decided if s["status"] == "completed")
            / max(1, len(decided))
            if decided else 0
        )

        # Average duration over completed runs only.
        durations = [
            self._row_duration_seconds(m) for s, m in rows
            if s["status"] == "completed"
        ]
        durations = [d for d in durations if d is not None]
        avg_secs = int(sum(durations) / len(durations)) if durations else 0

        self._tile_total.configure(text=f"{total}")
        self._tile_today.configure(text=f"{today_count}")
        self._tile_success.configure(
            text=f"{int(round(success_rate))}%" if decided else "—"
        )
        self._tile_avg.configure(
            text=self._format_secs(avg_secs) if avg_secs else "—"
        )

        # Quota card (today's runs vs RPD ceiling). Numbers come from
        # core.quotas, keyed off the user's currently-picked model —
        # picking a higher-tier model should immediately raise the
        # bar's ceiling, not still claim flash-lite's 500/day.
        # v2.5.0: framed as estimate. Google rotates free-tier
        # ceilings without notice and our static table can drift.
        from core.quotas import get_quota
        q = get_quota(self.app.app_state.model)
        self._quota_label.configure(
            text=f"{today_count} runs today  /  ~{q.rpd} free-tier est"
        )
        self._quota_bar.set(min(1.0, today_count / max(1, q.rpd)))
        self._quota_caption.configure(
            text=f"~RPM {q.rpm}   ·   "
                 f"~TPM {q.tpm:,}   ·   "
                 f"resets at midnight Pacific · verify at ai.google.dev"
        )

        # Mode split.
        quick = sum(1 for _, m in rows
                    if (m.get("mode") or "quick").lower() == "quick")
        thorough = total - quick
        denom = max(1, total)
        self._mode_quick_label.configure(
            text=f"Quick   {quick} runs   ({100*quick/denom:.0f}%)"
        )
        self._mode_quick_bar.set(quick / denom)
        self._mode_thorough_label.configure(
            text=f"Thorough   {thorough} runs   ({100*thorough/denom:.0f}%)"
        )
        self._mode_thorough_bar.set(thorough / denom)

        # Last 7 days.
        # v2.8.0 (Cos audit B-19): previously each _refresh tick destroyed
        # all 21 widgets in the week card and rebuilt them from scratch.
        # That caused a visible flicker every refresh + wasted Tk widget
        # IDs. Now we lazy-init the row widgets ONCE in
        # `_init_week_row_widgets()` (cached on self._week_widgets) and
        # update text/bar values in place via `.configure()` + `.set()`.
        day_buckets = {}
        for _, m in rows:
            d = self._row_date(m)
            if d is None:
                continue
            day_buckets[d] = day_buckets.get(d, 0) + 1
        max_in_week = max(
            [day_buckets.get(today - timedelta(days=i), 0)
             for i in range(7)] + [1]
        )

        if not hasattr(self, "_week_widgets") or not self._week_widgets:
            self._init_week_row_widgets()

        for i in range(7):
            day = today - timedelta(days=(6 - i))
            count = day_buckets.get(day, 0)
            label = "Today" if day == today else day.strftime("%a")
            is_today = (day == today)
            color = theme.ACCENT if is_today else theme.TEXT_SUB
            bar_color = theme.ACCENT if is_today else theme.ACCENT_2

            day_lbl, bar_w, count_lbl = self._week_widgets[i]
            day_lbl.configure(text=label, text_color=color)
            bar_w.configure(progress_color=bar_color)
            bar_w.set(count / max_in_week if max_in_week else 0)
            count_lbl.configure(text=str(count), text_color=color)

    def _init_week_row_widgets(self) -> None:
        """v2.8.0 (B-19): create the 21 widgets ONCE and keep refs in
        `self._week_widgets = [(day_lbl, bar, count_lbl), ...]` so
        `_refresh()` can update them in place instead of destroy/recreate."""
        for child in self._week_card.winfo_children():
            child.destroy()
        self._week_card.grid_columnconfigure(0, weight=0)
        self._week_card.grid_columnconfigure(1, weight=1)
        self._week_card.grid_columnconfigure(2, weight=0)

        self._week_widgets = []
        for i in range(7):
            day_lbl = ctk.CTkLabel(
                self._week_card, text="",
                font=theme.FONT_TINY, text_color=theme.TEXT_SUB,
                anchor="w", width=46,
            )
            day_lbl.grid(row=i, column=0, sticky="w", pady=theme.S1)

            bar = ctk.CTkProgressBar(
                self._week_card,
                progress_color=theme.ACCENT_2,
                fg_color=theme.BG_INPUT, height=6, corner_radius=3,
            )
            bar.set(0)
            bar.grid(row=i, column=1, sticky="ew",
                     padx=theme.S3, pady=theme.S1)

            count_lbl = ctk.CTkLabel(
                self._week_card, text="0",
                font=theme.FONT_TINY, text_color=theme.TEXT_SUB,
                anchor="e", width=28,
            )
            count_lbl.grid(row=i, column=2, sticky="e", pady=theme.S1)
            self._week_widgets.append((day_lbl, bar, count_lbl))

    # ── Parsing helpers ──────────────────────────────────────────────────
    def _row_date(self, meta: dict):
        ts = meta.get("created_at") or meta.get("started_at")
        try:
            if ts:
                return datetime.fromisoformat(ts).date()
        except Exception:
            pass
        return None

    def _row_duration_seconds(self, meta: dict):
        start = meta.get("started_at") or meta.get("created_at")
        end = meta.get("completed_at")
        if not start or not end:
            return None
        try:
            d = datetime.fromisoformat(end) - datetime.fromisoformat(start)
            return int(d.total_seconds())
        except Exception:
            return None

    def _format_secs(self, secs: int) -> str:
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m"
        return f"{mins // 60}h {mins % 60}m"
