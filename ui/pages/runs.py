"""Runs — full pipeline history with filter + table."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from pipeline import delete_session, list_sessions, load_session

from ui import theme
from ui.components.status_dot import status_dot
from ui.emoji_image import emoji_for


_STATUS_FILTERS = ["All", "Completed", "Running", "Stopped", "Failed"]
_MODE_FILTERS = ["All", "Quick", "Thorough"]


class RunsPage(ctk.CTkFrame):
    PAGE_ID = "runs"

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True,
                   padx=theme.PADDING_PAGE, pady=theme.PADDING_PAGE)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(4, weight=1)

        # ── Header (emoji + title + subtitle + count pill) ──────────────
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        head.grid_columnconfigure(1, weight=1)

        runs_emoji = emoji_for("📋", 28)
        if runs_emoji is not None:
            ctk.CTkLabel(head, image=runs_emoji, text="").grid(
                row=0, column=0, rowspan=2, sticky="w",
                padx=(0, theme.S3),
            )

        ctk.CTkLabel(
            head, text="Runs", anchor="w",
            font=theme.FONT_HEADING, text_color=theme.TEXT,
        ).grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(
            head, text="Every pipeline you've run on this machine.",
            anchor="w", font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=1, sticky="ew", pady=(theme.S1, 0))

        self.count_pill = ctk.CTkLabel(
            head, text="",
            font=theme.FONT_TINY, text_color=theme.TEXT_SUB,
            fg_color=theme.BG_CARD,
            corner_radius=theme.RADIUS_PILL,
            padx=theme.S3, pady=theme.S1,
        )
        self.count_pill.grid(row=0, column=2, rowspan=2,
                             sticky="e", padx=(theme.S3, 0))

        ctk.CTkFrame(
            outer, fg_color=theme.BORDER_DIM, height=1, corner_radius=0,
        ).grid(row=1, column=0, sticky="ew",
               pady=(theme.S3, theme.S4))

        # ── Filter bar ──────────────────────────────────────────────────
        filt = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        filt.grid(row=2, column=0, sticky="ew", pady=(0, theme.S3))
        filt.grid_columnconfigure(5, weight=1)

        def _label(parent, text, col):
            ctk.CTkLabel(
                parent, text=text,
                font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
                anchor="w",
            ).grid(row=0, column=col, sticky="w",
                   padx=(theme.S4 if col == 0 else theme.S3, theme.S1),
                   pady=theme.S3)

        _label(filt, "STATUS", 0)
        self.status_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            filt, values=_STATUS_FILTERS, variable=self.status_var,
            command=lambda _: self._refresh(),
            fg_color=theme.BG_INPUT,
            button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT,
            dropdown_fg_color=theme.BG_CARD,
            dropdown_text_color=theme.TEXT,
            dropdown_hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_BODY, height=32, width=120,
        ).grid(row=0, column=1, padx=(0, theme.S3),
               pady=theme.S3, sticky="w")

        _label(filt, "MODE", 2)
        self.mode_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            filt, values=_MODE_FILTERS, variable=self.mode_var,
            command=lambda _: self._refresh(),
            fg_color=theme.BG_INPUT,
            button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT,
            dropdown_fg_color=theme.BG_CARD,
            dropdown_text_color=theme.TEXT,
            dropdown_hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_BODY, height=32, width=120,
        ).grid(row=0, column=3, padx=(0, theme.S3),
               pady=theme.S3, sticky="w")

        _label(filt, "SEARCH", 4)
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh())
        self.search_entry = ctk.CTkEntry(
            filt, textvariable=self.search_var,
            placeholder_text="Filter by task text...",
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_DIM,
            text_color=theme.TEXT,
            font=theme.FONT_BODY, height=32,
        )
        self.search_entry.grid(row=0, column=5, padx=(0, theme.S3),
                                pady=theme.S3, sticky="ew")

        ctk.CTkButton(
            filt, text="Refresh",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.TEXT,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BORDER,
            font=theme.FONT_BODY, height=32, width=90,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._refresh,
        ).grid(row=0, column=6, padx=(0, theme.S4),
               pady=theme.S3, sticky="e")

        # ── Table header row (sticky outside scrollable area) ───────────
        table_head = ctk.CTkFrame(outer, fg_color="transparent")
        table_head.grid(row=3, column=0, sticky="ew", pady=(theme.S2, 0))
        self._configure_table_columns(table_head)
        for col, text in [(0, ""), (1, "TASK"), (2, "MODE"),
                          (3, "DURATION"), (4, "WHEN"), (5, "")]:
            ctk.CTkLabel(
                table_head, text=text,
                font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
                anchor="w",
            ).grid(row=0, column=col, sticky="ew",
                   padx=(theme.S2 if col else theme.S4, 0),
                   pady=(0, theme.S2))

        ctk.CTkFrame(
            outer, fg_color=theme.BORDER_DIM, height=1, corner_radius=0,
        ).grid(row=4, column=0, sticky="new")

        # ── Scrollable table body ───────────────────────────────────────
        self.body_card = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        self.body_card.grid(row=4, column=0, sticky="nsew",
                            pady=(theme.S3, 0))
        self.body_card.grid_columnconfigure(0, weight=1)
        self.body_card.grid_rowconfigure(0, weight=1)

        self.body = ctk.CTkScrollableFrame(
            self.body_card, fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.BORDER_DIM,
            label_text="",
        )
        self.body.grid(row=0, column=0, sticky="nsew",
                       padx=theme.S2, pady=theme.S2)

    # ── Layout helper ────────────────────────────────────────────────────
    def _configure_table_columns(self, frame) -> None:
        # col 0: dot, col 1: task (grows), col 2: mode, col 3: duration,
        # col 4: when, col 5: delete
        frame.grid_columnconfigure(0, weight=0, minsize=24)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=0, minsize=96)
        frame.grid_columnconfigure(3, weight=0, minsize=104)
        frame.grid_columnconfigure(4, weight=0, minsize=110)
        frame.grid_columnconfigure(5, weight=0, minsize=32)

    # ── Lifecycle ────────────────────────────────────────────────────────
    def on_show(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

        try:
            sessions = list_sessions()
        except Exception:
            sessions = []

        status_filter = self.status_var.get().lower()
        mode_filter = self.mode_var.get().lower()
        search = self.search_var.get().strip().lower()

        filtered = []
        for s in sessions:
            if status_filter != "all" and s["status"] != status_filter:
                continue
            meta = self._read_meta(s["path"])
            mode = (meta.get("mode") or "quick").lower()
            if mode_filter != "all" and mode != mode_filter:
                continue
            if search and search not in (s["task_preview"] or "").lower():
                continue
            filtered.append((s, meta))

        self.count_pill.configure(
            text=f"{len(filtered)} of {len(sessions)}"
                 if (status_filter != "all" or mode_filter != "all"
                     or search)
                 else f"{len(sessions)} total"
        )

        if not filtered:
            ctk.CTkLabel(
                self.body,
                text=("No runs match these filters."
                      if sessions else
                      "No runs yet. Compose a task on Home."),
                font=theme.FONT_SMALL, text_color=theme.TEXT_DIM,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew",
                   pady=theme.S5, padx=theme.S4)
            return

        for i, (s, meta) in enumerate(filtered):
            self._build_row(self.body, row=i, s=s, meta=meta)

    def _build_row(self, parent, *, row: int, s: dict, meta: dict) -> None:
        bg = theme.BG_TABLE_ROW_ALT if row % 2 else "transparent"
        row_frame = ctk.CTkFrame(
            parent, fg_color=bg,
            corner_radius=theme.RADIUS_SMALL,
        )
        row_frame.grid(row=row, column=0, sticky="ew", pady=1, padx=2)
        self._configure_table_columns(row_frame)

        status = s["status"]
        dot_color = {
            "completed": theme.ONLINE,
            "running":   theme.ACCENT,
            "stopped":   theme.WARN,
            "failed":    theme.OFFLINE,
        }.get(status, theme.TEXT_DIM)
        status_dot(row_frame, color=dot_color, size=10).grid(
            row=0, column=0, padx=(theme.S3, theme.S2), pady=theme.S2
        )

        preview = (s["task_preview"] or "(empty)").strip()
        short = preview[:120] + ("..." if len(preview) > 120 else "")
        ctk.CTkButton(
            row_frame, text=short, anchor="w", height=30,
            fg_color="transparent",
            text_color=theme.TEXT_SUB,
            hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_SMALL,
            command=lambda sp=s["path"], st=status:
                self._open(sp, st),
        ).grid(row=0, column=1, sticky="ew", padx=(0, theme.S2))

        # MODE column
        mode = (meta.get("mode") or "quick").capitalize()
        ctk.CTkLabel(
            row_frame, text=mode,
            font=theme.FONT_TINY, text_color=theme.TEXT_SUB,
            anchor="w",
        ).grid(row=0, column=2, sticky="w", padx=(0, theme.S2))

        # DURATION column
        dur = self._duration_label(meta, status)
        ctk.CTkLabel(
            row_frame, text=dur,
            font=theme.FONT_TINY, text_color=theme.TEXT_SUB,
            anchor="w",
        ).grid(row=0, column=3, sticky="w", padx=(0, theme.S2))

        # WHEN column
        when = self._when_label(meta, s["path"])
        ctk.CTkLabel(
            row_frame, text=when,
            font=theme.FONT_TINY, text_color=theme.TEXT_DIM,
            anchor="w",
        ).grid(row=0, column=4, sticky="w", padx=(0, theme.S2))

        # Delete X
        ctk.CTkButton(
            row_frame, text="x", width=24, height=24,
            fg_color="transparent",
            text_color=theme.TEXT_DIM,
            hover_color="#3a1f1f",
            font=theme.FONT_TINY,
            command=lambda sp=s["path"]: self._delete(sp),
        ).grid(row=0, column=5, sticky="e", padx=(0, theme.S2))

    # ── Helpers ──────────────────────────────────────────────────────────
    def _read_meta(self, sp: Path) -> dict:
        try:
            return json.loads(
                (sp / "_meta.json").read_text(encoding="utf-8")
            )
        except Exception:
            return {}

    def _duration_label(self, meta: dict, status: str) -> str:
        # Best-effort: started_at -> completed_at/stopped_at/failed_at.
        start = meta.get("started_at") or meta.get("created_at")
        end = (meta.get("completed_at") or meta.get("stopped_at")
               or meta.get("failed_at"))
        if status == "running":
            return "running..."
        if not start or not end:
            return "-"
        try:
            d = datetime.fromisoformat(end) - datetime.fromisoformat(start)
            secs = int(d.total_seconds())
            if secs < 60:
                return f"{secs}s"
            mins = secs // 60
            if mins < 60:
                return f"{mins}m {secs % 60}s"
            return f"{mins // 60}h {mins % 60}m"
        except Exception:
            return "-"

    def _when_label(self, meta: dict, path: Path) -> str:
        ts = meta.get("created_at") or meta.get("started_at")
        try:
            if ts:
                dt = datetime.fromisoformat(ts)
                delta = datetime.now() - dt
                if delta.days >= 1:
                    return f"{delta.days}d ago"
                hours = delta.seconds // 3600
                if hours >= 1:
                    return f"{hours}h ago"
                mins = max(1, delta.seconds // 60)
                return f"{mins}m ago"
        except Exception:
            pass
        return path.name[:10]

    def _open(self, sp: Path, status: str) -> None:
        # Guard: don't reassign session_path while a pipeline is running
        # in another session (would break Running page's live counters).
        if (self.app.app_state.running
                and self.app.app_state.current_session_path is not None
                and self.app.app_state.current_session_path != sp):
            messagebox.showinfo(
                "Pipeline running",
                "Finish or stop the current pipeline first before "
                "opening another session.",
            )
            self.app.show_page("running")
            return
        try:
            data = load_session(sp)
        except Exception as e:
            messagebox.showerror("Could not open session", str(e))
            return
        self.app.app_state.current_session_path = sp
        self.app.app_state.current_outputs = data["outputs"]
        # Stale status="running" (from a crashed previous run) → still
        # land on Done so the user sees partial output instead of an
        # empty Running page wired to a dead pipeline.
        is_live = (self.app.app_state.running
                   and self.app.app_state.current_session_path == sp)
        self.app.show_page("running" if is_live else "done")

    def _delete(self, sp: Path) -> None:
        if not messagebox.askyesno(
            "Delete session?", f"Delete '{sp.name}'?"
        ):
            return
        try:
            delete_session(sp)
            if self.app.app_state.current_session_path == sp:
                self.app.app_state.current_session_path = None
            self._refresh()
        except Exception as e:
            messagebox.showerror("Could not delete", str(e))
