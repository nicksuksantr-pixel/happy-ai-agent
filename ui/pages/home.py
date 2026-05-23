"""Home — compose-first layout.

The page is one big Compose card filling the available height + a short
Recent runs strip below. No stat cards (they didn't survive the v2.1.0
review — they pretended to be useful but didn't help anyone).

Top-right of the page has a "Tune" gear that opens Settings — so options
are reachable without leaving Home.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from file_loader import is_supported
from pipeline import list_sessions, load_session

from ui import theme
from ui.components.placeholder_textbox import PlaceholderTextbox
from ui.components.status_dot import status_dot
from ui.emoji_image import emoji_for


class HomePage(ctk.CTkFrame):
    PAGE_ID = "home"

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app

        # Outer frame controls page padding + row weights.
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True,
                   padx=theme.PADDING_PAGE, pady=theme.PADDING_PAGE)
        outer.grid_columnconfigure(0, weight=1)
        # Row layout:
        #   0 = header  /  1 = divider  /  2 = auth warning (conditional)
        #   3 = compose card (grows)    /  4 = recent runs (fixed-ish)
        outer.grid_rowconfigure(3, weight=1)

        # ── Page header (emoji + title + subtitle + Tune gear) ─────────
        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        home_emoji = emoji_for("🏠", 28)
        if home_emoji is not None:
            ctk.CTkLabel(header, image=home_emoji, text="").grid(
                row=0, column=0, rowspan=2, sticky="w",
                padx=(0, theme.S3),
            )

        ctk.CTkLabel(
            header, text="Home", anchor="w",
            font=theme.FONT_HEADING, text_color=theme.TEXT,
        ).grid(row=0, column=1, sticky="ew")

        # Subtitle on the same band as Tune.
        ctk.CTkLabel(
            header,
            text="Compose a task. The AI team takes it from there.",
            anchor="w", font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=1, sticky="ew", pady=(theme.S1, 0))

        # Tune gear -> Settings.
        gear_img = emoji_for("⚙", 16)
        self.tune_btn = ctk.CTkButton(
            header,
            text="  Tune" if gear_img else ":  Tune",
            image=gear_img, compound="left",
            fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_SUB,
            border_width=1, border_color=theme.BORDER,
            font=theme.FONT_BODY, height=34, width=96,
            corner_radius=theme.RADIUS_BUTTON,
            command=lambda: self.app.show_page("settings"),
        )
        self.tune_btn.grid(row=0, column=2, rowspan=2,
                           sticky="e", padx=(theme.S3, 0))

        ctk.CTkFrame(
            outer, fg_color=theme.BORDER_DIM, height=1, corner_radius=0,
        ).grid(row=1, column=0, sticky="ew",
               pady=(theme.S3, theme.S4))

        # ── Auth gate (gridded conditionally in on_show) ────────────────
        self.auth_warn = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.WARN, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        self.auth_warn.grid_columnconfigure(1, weight=1)
        status_dot(self.auth_warn, color=theme.WARN, size=10).grid(
            row=0, column=0, padx=(theme.S4, theme.S3), pady=theme.S4,
        )
        ctk.CTkLabel(
            self.auth_warn,
            text="No Gemini connection. Open Settings to paste an API key.",
            font=theme.FONT_BODY_BOLD, text_color=theme.WARN,
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", pady=theme.S4)
        ctk.CTkButton(
            self.auth_warn, text="Open Settings",
            fg_color=theme.WARN, hover_color="#d97706",
            text_color="white",
            font=theme.FONT_BODY_BOLD, height=32,
            corner_radius=theme.RADIUS_BUTTON,
            command=lambda: self.app.show_page("settings"),
        ).grid(row=0, column=2, padx=(theme.S2, theme.S4), pady=theme.S3)

        # ── COMPOSE CARD (the action) ──────────────────────────────────
        self.compose = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        self.compose.grid(row=3, column=0, sticky="nsew",
                          pady=(0, theme.S4))
        self.compose.grid_columnconfigure(0, weight=1)
        # Row 1 = task input grows to fill card.
        self.compose.grid_rowconfigure(1, weight=1)

        # Compose header (emoji + overline label).
        compose_head = ctk.CTkFrame(self.compose, fg_color="transparent")
        compose_head.grid(row=0, column=0, sticky="ew",
                          padx=theme.PADDING_CARD,
                          pady=(theme.PADDING_CARD, theme.S2))
        compose_head.grid_columnconfigure(1, weight=1)
        task_emoji = emoji_for("✏️", 16)
        if task_emoji is not None:
            ctk.CTkLabel(compose_head, image=task_emoji, text="").grid(
                row=0, column=0, sticky="w", padx=(0, theme.S2),
            )
        ctk.CTkLabel(
            compose_head, text="TASK",
            font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        # The textbox is what grows when the window grows.
        # PlaceholderTextbox auto-hides the example on focus/keypress
        # and restores it on focus-out when empty — replaces the
        # previous "hard-coded example that users had to delete by
        # hand" pattern.
        self.task_input = PlaceholderTextbox(
            self.compose,
            placeholder=(
                "Describe what you want the AI team to build.\n"
                "Example: Build a single-file HTML calculator with 0-9 "
                "keys, +  -  ×  ÷, =, C — modern flat design, works on "
                "mobile too."
            ),
            placeholder_color=theme.TEXT_DIM,
            text_color=theme.TEXT,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_DIM,
            border_width=1,
            corner_radius=theme.RADIUS_CARD,
            font=theme.FONT_BODY,
            wrap="word",
        )
        self.task_input.grid(row=1, column=0, sticky="nsew",
                             padx=theme.PADDING_CARD,
                             pady=(0, theme.S3))

        # Separator above the options strip.
        ctk.CTkFrame(
            self.compose, fg_color=theme.BORDER_DIM, height=1,
            corner_radius=0,
        ).grid(row=2, column=0, sticky="ew",
               padx=theme.PADDING_CARD, pady=(0, theme.S3))

        # Options strip — two stacked rows so it fits at minsize (920 px).
        #  Row A: [Mode segmented]            [Attach btn]
        #  Row B: meta hint                    [Run Pipeline >>]
        opt = ctk.CTkFrame(self.compose, fg_color="transparent")
        opt.grid(row=3, column=0, sticky="ew",
                 padx=theme.PADDING_CARD,
                 pady=(0, theme.PADDING_CARD))
        opt.grid_columnconfigure(0, weight=1)
        opt.grid_columnconfigure(1, weight=0)

        # ── Row A: Mode segmented + Attach button ──────────────────────
        row_a = ctk.CTkFrame(opt, fg_color="transparent")
        row_a.grid(row=0, column=0, columnspan=2, sticky="ew",
                   pady=(0, theme.S2))
        row_a.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row_a, text="MODE",
            font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, theme.S3))

        self.mode_var = ctk.StringVar(
            value="Thorough" if self.app.app_state.pipeline_mode ==
                                "thorough" else "Quick"
        )
        self._mode_seg = ctk.CTkSegmentedButton(
            row_a, values=["Quick", "Thorough"],
            variable=self.mode_var,
            command=self._on_mode_change,
            fg_color=theme.BG_INPUT,
            selected_color=theme.ACCENT,
            selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.BG_CARD_HOVER,
            unselected_hover_color=theme.BORDER,
            text_color=theme.TEXT,
            font=theme.FONT_BODY_BOLD,
        )
        self._mode_seg.grid(row=0, column=1, sticky="w")

        self.attach_summary = ctk.CTkLabel(
            row_a, text="0 attached",
            font=theme.FONT_TINY, text_color=theme.TEXT_DIM,
            anchor="e",
        )
        self.attach_summary.grid(row=0, column=2, sticky="e",
                                 padx=(0, theme.S2))

        self.attach_btn = ctk.CTkButton(
            row_a, text="Attach files",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.TEXT_SUB,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BORDER,
            font=theme.FONT_TINY, height=32, width=110,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._pick_files,
        )
        self.attach_btn.grid(row=0, column=3, sticky="e")

        # ── Row B: meta hint + Run Pipeline CTA ────────────────────────
        row_b = ctk.CTkFrame(opt, fg_color="transparent")
        row_b.grid(row=1, column=0, columnspan=2, sticky="ew")
        row_b.grid_columnconfigure(0, weight=1)

        self.meta_label = ctk.CTkLabel(
            row_b, text="",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
            anchor="w", wraplength=520, justify="left",
        )
        self.meta_label.grid(row=0, column=0, sticky="ew",
                             padx=(0, theme.S3))

        play_img = emoji_for("▶️", 18)
        self.start_btn = ctk.CTkButton(
            row_b,
            text="  Run Pipeline" if play_img else ">  Run Pipeline",
            image=play_img, compound="left",
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color="white",
            font=(theme.FAMILY, 13, "bold"),
            height=44, width=180,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._start,
        )
        self.start_btn.grid(row=0, column=1, sticky="e")

        # ── Recent runs strip (compact — 3 entries + "View all") ────────
        self.recent_card = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        self.recent_card.grid(row=4, column=0, sticky="ew")
        self.recent_card.grid_columnconfigure(0, weight=1)

        recent_head = ctk.CTkFrame(self.recent_card, fg_color="transparent")
        recent_head.grid(row=0, column=0, sticky="ew",
                         padx=theme.PADDING_CARD,
                         pady=(theme.PADDING_CARD, theme.S2))
        recent_head.grid_columnconfigure(1, weight=1)
        clock_emoji = emoji_for("🕒", 16)
        if clock_emoji is not None:
            ctk.CTkLabel(recent_head, image=clock_emoji, text="").grid(
                row=0, column=0, sticky="w", padx=(0, theme.S2),
            )
        ctk.CTkLabel(
            recent_head, text="RECENT RUNS",
            font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        self.view_all_btn = ctk.CTkButton(
            recent_head, text="View all  ->",
            fg_color="transparent", text_color=theme.ACCENT,
            hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_TINY, height=22,
            corner_radius=theme.RADIUS_SMALL,
            command=lambda: self.app.show_page("runs"),
        )
        self.view_all_btn.grid(row=0, column=2, sticky="e")

        self.recent_body = ctk.CTkFrame(
            self.recent_card, fg_color="transparent"
        )
        self.recent_body.grid(row=1, column=0, sticky="ew",
                              padx=theme.PADDING_CARD,
                              pady=(0, theme.PADDING_CARD))
        self.recent_body.grid_columnconfigure(0, weight=1)

    # ── Lifecycle ────────────────────────────────────────────────────────
    def on_show(self) -> None:
        s = self.app.app_state

        # Auth gate sits in dedicated row 2 (between divider at row 1 and
        # compose card at row 3) — no overlap, gridded on demand.
        if not s.auth_ready:
            self.auth_warn.grid(row=2, column=0, sticky="ew",
                                pady=(0, theme.S4))
            self.start_btn.configure(state="disabled")
        else:
            self.auth_warn.grid_remove()
            self.start_btn.configure(state="normal")

        # Attach UI visibility (Thorough only).
        is_thorough = s.pipeline_mode == "thorough"
        self.attach_btn.configure(
            state="normal" if is_thorough else "disabled",
        )
        n = len(s.attached_files)
        if not is_thorough:
            self.attach_summary.configure(
                text="Thorough only", text_color=theme.TEXT_DIM,
            )
        elif n:
            kb = sum(len(b) for _, b in s.attached_files) / 1024
            self.attach_summary.configure(
                text=f"{n} attached  ({kb:.0f} KB)",
                text_color=theme.TEXT_SUB,
            )
        else:
            self.attach_summary.configure(
                text="0 attached", text_color=theme.TEXT_DIM,
            )

        self.meta_label.configure(
            text=f"{self._short_model()}   ·   "
                 f"delay {s.delay}s   ·   "
                 f"judge >= {s.judge_threshold}/100   ·   "
                 f"loops {s.max_judge_loops}"
        )

        self._refresh_recent()

    def focus_task(self) -> None:
        try:
            self.task_input.focus_set()
        except Exception:
            pass

    def _short_model(self) -> str:
        m = self.app.app_state.model or "(none)"
        return m.replace("gemini-", "")

    # ── Recent runs strip ────────────────────────────────────────────────
    def _refresh_recent(self) -> None:
        for child in self.recent_body.winfo_children():
            child.destroy()
        try:
            sessions = list_sessions()
        except Exception:
            sessions = []
        if not sessions:
            ctk.CTkLabel(
                self.recent_body,
                text="No runs yet. Compose a task above and hit Run.",
                font=theme.FONT_SMALL, text_color=theme.TEXT_DIM,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", pady=theme.S2)
            return

        for i, s in enumerate(sessions[:3]):
            self._build_recent_row(self.recent_body, row=i, s=s)

    def _build_recent_row(self, parent, *, row: int, s: dict) -> None:
        row_frame = ctk.CTkFrame(
            parent, fg_color="transparent",
            corner_radius=theme.RADIUS_SMALL,
        )
        row_frame.grid(row=row, column=0, sticky="ew", pady=theme.S1)
        row_frame.grid_columnconfigure(1, weight=1)

        status = s["status"]
        dot_color = {
            "completed": theme.ONLINE,
            "running":   theme.ACCENT,
            "stopped":   theme.WARN,
            "failed":    theme.OFFLINE,
        }.get(status, theme.TEXT_DIM)
        status_dot(row_frame, color=dot_color, size=10).grid(
            row=0, column=0, padx=(theme.S2, theme.S3), pady=theme.S2
        )

        preview = (s["task_preview"] or "(empty)").strip()
        short = preview[:80] + ("..." if len(preview) > 80 else "")
        ctk.CTkButton(
            row_frame, text=short, anchor="w", height=30,
            fg_color="transparent",
            text_color=theme.TEXT_SUB,
            hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_SMALL,
            command=lambda sp=s["path"], st=status:
                self._open_session(sp, st),
        ).grid(row=0, column=1, sticky="ew", padx=(0, theme.S3))

        when = self._when_label(s)
        ctk.CTkLabel(
            row_frame, text=f"{status}   ·   {when}",
            font=theme.FONT_TINY, text_color=theme.TEXT_DIM,
            anchor="e",
        ).grid(row=0, column=2, sticky="e", padx=(0, theme.S3))

    def _when_label(self, s: dict) -> str:
        try:
            meta_path = s["path"] / "_meta.json"
            if meta_path.exists():
                import json
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                ts = meta.get("created_at") or meta.get("started_at")
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
        return s["path"].name[:10]

    def _open_session(self, sp: Path, status: str) -> None:
        # Guard: never swap session_path out from under a live pipeline.
        # current_session_path is the one the runner is writing into; if
        # the user clicked a different session while a pipeline is
        # running, point them at the live one + complain.
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
        # Open Running only if this IS the live session of a running
        # pipeline. A status="running" in meta from a previous crashed
        # run is stale — show Done so the user can see partial output
        # instead of an empty Running page wired to a dead runner.
        is_live = (self.app.app_state.running
                   and self.app.app_state.current_session_path == sp)
        self.app.show_page("running" if is_live else "done")

    # ── Mode + attach handlers ──────────────────────────────────────────
    def _on_mode_change(self, value: str) -> None:
        self.app.app_state.pipeline_mode = (
            "thorough" if value.lower().startswith("thorough") else "quick"
        )
        self.app.app_state.persist()
        self.on_show()

    def _pick_files(self) -> None:
        if self.app.app_state.pipeline_mode != "thorough":
            messagebox.showinfo(
                "Thorough mode only",
                "File attachments are only used by the Thorough pipeline.\n"
                "Switch the Mode toggle to Thorough first.",
            )
            return
        paths = filedialog.askopenfilenames(
            title="Attach reference files",
            filetypes=[
                ("Supported",
                 "*.png *.jpg *.jpeg *.webp *.gif *.pdf "
                 "*.docx *.xlsx *.csv *.txt *.md"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        files = []
        for p in paths:
            try:
                if is_supported(p):
                    files.append((Path(p).name, Path(p).read_bytes()))
            except Exception:
                pass
        self.app.app_state.attached_files = files
        self.on_show()

    # ── Start ────────────────────────────────────────────────────────────
    def _start(self) -> None:
        if not self.app.app_state.auth_ready:
            messagebox.showwarning(
                "Not connected",
                "Open Settings and paste a Gemini API key first.",
            )
            self.app.show_page("settings")
            return
        # get_real_text() returns "" when only the placeholder is shown,
        # so an unedited textbox correctly trips the "empty task" guard
        # instead of submitting the example as the user's prompt.
        task = self.task_input.get_real_text().strip()
        if not task:
            messagebox.showwarning(
                "Empty task",
                "Type the task you want the AI team to work on.",
            )
            return
        s = self.app.app_state
        settings = {
            "delay": s.delay,
            "judge_threshold": s.judge_threshold,
            "max_judge_loops": s.max_judge_loops,
            "mode": s.pipeline_mode,
        }
        self.app.start_pipeline(task, settings)
