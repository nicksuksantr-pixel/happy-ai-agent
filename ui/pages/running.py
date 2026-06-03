"""Running — live pipeline progress.

Top card: title + elapsed timer + progress bar + Stop button.
Bottom: agent timeline (left, status_dot + name + judge score) + live
output viewer (right, markdown + pygments).
"""
from __future__ import annotations

import json
import time
from tkinter import messagebox

import customtkinter as ctk

from agents import get_phases_for_mode
from core.quotas import get_quota  # v2.8.0 (Cos audit B-09): hoisted from __init__

from ui import theme
from ui.components.agent_row import AgentRowWidgets
from ui.components.output_view import create_output_text, render_output_to_textbox
from ui.components.page_header import page_header
from ui.components.status_dot import status_dot


class RunningPage(ctk.CTkFrame):
    PAGE_ID = "running"

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=22, pady=18)
        outer.grid_columnconfigure(1, weight=1)
        # Row 4 = the two-pane (agent list + output) grows.
        outer.grid_rowconfigure(4, weight=1)

        page_header(outer, title="Running",
                    subtitle="The AI team is working — live agent progress.",
                    emoji="🤖", row=0)

        # ── Progress card (top, full width) ─────────────────────────────
        prog = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        prog.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 12))
        prog.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(prog, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew",
                       padx=16, pady=(14, 4))
        title_row.grid_columnconfigure(1, weight=1)

        self._running_dot = status_dot(title_row,
                                        color=theme.ACCENT, size=12)
        self._running_dot.grid(row=0, column=0, padx=(0, 10))

        self.title_label = ctk.CTkLabel(
            title_row, text="Team working",
            font=theme.FONT_SUBHEAD, text_color=theme.ACCENT, anchor="w",
        )
        self.title_label.grid(row=0, column=1, sticky="ew")

        self.elapsed_label = ctk.CTkLabel(
            title_row, text="00:00",
            font=(theme.FAMILY_MONO, 13, "bold"),
            text_color=theme.TEXT_SUB, anchor="e",
        )
        self.elapsed_label.grid(row=0, column=2, sticky="e")

        self.progress_label = ctk.CTkLabel(
            prog, text="",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.progress_label.grid(row=1, column=0, sticky="ew",
                                 padx=16, pady=(0, 6))

        self.progress = ctk.CTkProgressBar(
            prog, progress_color=theme.ACCENT,
            fg_color=theme.BG_INPUT, height=10, corner_radius=5,
        )
        self.progress.set(0)
        self.progress.grid(row=2, column=0, sticky="ew",
                           padx=16, pady=(0, 10))

        actions = ctk.CTkFrame(prog, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))
        self.stop_btn = ctk.CTkButton(
            actions, text="Stop pipeline",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.OFFLINE,
            border_width=1, border_color=theme.OFFLINE,
            hover_color="#3a1f1f",
            font=theme.FONT_BODY_BOLD,
            corner_radius=theme.RADIUS_BUTTON, height=34,
            command=self._stop,
        )
        self.stop_btn.pack(side="left")

        # ── Rate limiter card (TPM watcher + RPD counter) ───────────────
        # All three numbers (TPM, RPM, RPD) come from core.quotas now —
        # each Gemini model has a different free-tier ceiling, and
        # hard-coding the flash-lite 250K/15/500 numbers everywhere
        # caused them to lie when the user picked any other model.
        # Initial labels use the current model's quota; refresh_rate_
        # limiter() reads it again on every tick so model changes
        # mid-run still update the bar.
        # v2.5.0: numbers are now framed as estimates ("~N") with a
        # caption pointing the user to Google's authoritative limits
        # page. The static table in core.quotas is best-effort —
        # Google rotates free-tier ceilings without bumping any
        # version, so claiming a hard "RPD cap 1000/day" is dishonest.
        # v2.8.0 (B-09): get_quota now imported at module top.
        q = get_quota(self.app.app_state.model)
        rate = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        rate.grid(row=3, column=0, columnspan=2, sticky="ew",
                  pady=(0, 12))
        rate.grid_columnconfigure(0, weight=1)
        rate.grid_columnconfigure(1, weight=1)

        # Left half: TPM bar
        tpm_box = ctk.CTkFrame(rate, fg_color="transparent")
        tpm_box.grid(row=0, column=0, sticky="ew",
                     padx=(16, 12), pady=14)
        tpm_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tpm_box, text="TPM USAGE  (rolling 60 s)",
            font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        self.tpm_label = ctk.CTkLabel(
            tpm_box, text=f"0 / {q.tpm:,}",
            font=(theme.FAMILY_MONO, 12, "bold"),
            text_color=theme.TEXT_SUB, anchor="w",
        )
        self.tpm_label.grid(row=1, column=0, sticky="ew",
                            pady=(theme.S1, theme.S2))
        self.tpm_bar = ctk.CTkProgressBar(
            tpm_box, progress_color=theme.ACCENT_3,
            fg_color=theme.BG_INPUT, height=8, corner_radius=4,
        )
        self.tpm_bar.set(0)
        self.tpm_bar.grid(row=2, column=0, sticky="ew")

        # Right half: RPD count + cap
        rpd_box = ctk.CTkFrame(rate, fg_color="transparent")
        rpd_box.grid(row=0, column=1, sticky="ew",
                     padx=(12, 16), pady=14)
        rpd_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            rpd_box, text="REQUESTS THIS RUN",
            font=theme.FONT_OVERLINE, text_color=theme.TEXT_DIM,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        self.rpd_label = ctk.CTkLabel(
            rpd_box, text=f"0  ·  free tier ~{q.rpd}/day (est)",
            font=(theme.FAMILY_MONO, 12, "bold"),
            text_color=theme.TEXT_SUB, anchor="w",
        )
        self.rpd_label.grid(row=1, column=0, sticky="ew",
                            pady=(theme.S1, theme.S2))
        self.rpd_caption = ctk.CTkLabel(
            rpd_box,
            text=f"~RPM {q.rpm} · adaptive throttle on · "
                 f"verify at ai.google.dev",
            font=theme.FONT_TINY, text_color=theme.TEXT_DIM,
            anchor="w",
        )
        self.rpd_caption.grid(row=2, column=0, sticky="ew")

        # ── Agent timeline (left) ───────────────────────────────────────
        self.agents_card = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD, width=300,
        )
        self.agents_card.grid(row=4, column=0, sticky="nsew",
                              pady=(0, 0), padx=(0, 10))
        self.agents_card.grid_columnconfigure(0, weight=1)
        self.agents_card.grid_rowconfigure(1, weight=1)
        self.agents_card.grid_propagate(False)

        ctk.CTkLabel(
            self.agents_card, text="AI TEAM",
            font=(theme.FAMILY, 9, "bold"),
            text_color=theme.TEXT_DIM, anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))

        self.agents_scroll = ctk.CTkScrollableFrame(
            self.agents_card, fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.BORDER_DIM,
            label_text="",
        )
        self.agents_scroll.grid(row=1, column=0, sticky="nsew",
                                 padx=8, pady=(0, 10))

        # ── Output viewer (right) ───────────────────────────────────────
        out = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        out.grid(row=4, column=1, sticky="nsew", pady=(0, 0))
        out.grid_columnconfigure(0, weight=1)
        out.grid_rowconfigure(1, weight=1)

        self.output_title = ctk.CTkLabel(
            out, text="OUTPUT — click an agent on the left",
            font=(theme.FAMILY, 9, "bold"),
            text_color=theme.TEXT_DIM, anchor="w",
        )
        self.output_title.grid(row=0, column=0, sticky="ew",
                               padx=16, pady=(14, 6))

        wrap, self.output_text = create_output_text(out)
        wrap.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self._agent_rows: dict = {}  # pid -> AgentRowWidgets(row, dot, name_btn, extra, phase_meta)
        self._tick_id = None
        self._pulse_step = 0  # cycles for animated dot on the running row

    # ── Lifecycle ────────────────────────────────────────────────────────
    def on_show(self) -> None:
        self._build_agent_list()
        self.refresh()
        self._tick()

    def _tick(self) -> None:
        if self.app.current_page != "running":
            self._tick_id = None
            return
        if self.app.app_state.started_at:
            elapsed = int(time.time() - self.app.app_state.started_at)
            self.elapsed_label.configure(
                text=f"{elapsed // 60:02d}:{elapsed % 60:02d}"
            )
        self._refresh_rate_limiter()
        self._pulse_running_dot()
        # Cancel before reschedule (lesson #14) so ticker chains don't pile.
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
        # Faster tick (500 ms) gives the pulse a softer rhythm.
        self._tick_id = self.after(500, self._tick)

    def _pulse_running_dot(self) -> None:
        """Cycle the currently-running agent's dot between accent and
        accent-light so it visibly pulses."""
        self._pulse_step = (self._pulse_step + 1) % 4
        # 4-step pulse: bright -> medium -> dim -> medium -> back.
        pulse_colors = [
            theme.ACCENT,            # bright
            "#FDBA74",               # orange-300, lighter
            "#FED7AA",               # orange-200, lighter still
            "#FDBA74",               # back to medium
        ]
        target_color = pulse_colors[self._pulse_step]

        s = self.app.app_state
        running_pid = next(
            (pid for pid, st in s.current_status.items() if st == "running"),
            None,
        )
        for pid, w in self._agent_rows.items():
            if pid == running_pid:
                w.dot.configure(fg_color=target_color)
                # Also pulse the title bar dot.
                try:
                    self._running_dot.configure(fg_color=target_color)
                except Exception:
                    pass

    def _refresh_rate_limiter(self) -> None:
        """Read live counters from the live PipelineRunner and update bars.

        PipelineRunner is created in HappyApp.start_pipeline and stored on
        `app_state.pipeline_runner`. Its `_tpm` is the rolling-60s tracker;
        `token_log` is the per-call usage list — we count its length for
        the requests counter.

        Quota numbers refresh from the current model on every tick so
        the labels stay accurate even if the user picks a different
        model after starting a run (the live ceiling is what the
        PipelineRunner enforces, but the UI should always reflect what
        the user picked LAST).
        """
        # v2.8.0 (B-09): get_quota imported at module top.
        runner = getattr(self.app.app_state, "pipeline_runner", None)
        if runner is None:
            return

        q = get_quota(self.app.app_state.model)

        # TPM rolling window.
        # v2.8.0 (Cos audit B-10): use the public accessor instead of
        # poking at `runner._tpm` directly.
        current = runner.current_tpm()
        ceiling = max(1, q.tpm)
        ratio = min(1.0, current / ceiling)
        self.tpm_bar.set(ratio)
        self.tpm_label.configure(text=f"{current:,} / {ceiling:,}")
        # Color the bar when approaching ceiling.
        if ratio >= 0.85:
            self.tpm_bar.configure(progress_color=theme.OFFLINE)
            self.tpm_label.configure(text_color=theme.OFFLINE)
        elif ratio >= 0.6:
            self.tpm_bar.configure(progress_color=theme.WARN)
            self.tpm_label.configure(text_color=theme.WARN)
        else:
            self.tpm_bar.configure(progress_color=theme.ACCENT_3)
            self.tpm_label.configure(text_color=theme.TEXT_SUB)

        # Request count this run + RPD + RPM caps (live with model).
        # v2.8.0 (Cos audit B-10): public accessor.
        req_count = runner.request_count()
        self.rpd_label.configure(
            text=f"{req_count}  ·  free tier ~{q.rpd}/day (est)"
        )
        self.rpd_caption.configure(
            text=f"~RPM {q.rpm} · adaptive throttle on · "
                 f"verify at ai.google.dev"
        )

    def destroy(self) -> None:
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None
        super().destroy()

    # ── Build / refresh ──────────────────────────────────────────────────
    def _build_agent_list(self) -> None:
        for child in self.agents_scroll.winfo_children():
            child.destroy()
        self._agent_rows.clear()

        mode = "quick"
        sp = self.app.app_state.current_session_path
        if sp:
            try:
                meta = json.loads(
                    (sp / "_meta.json").read_text(encoding="utf-8")
                )
                mode = meta.get("mode", "quick")
            except Exception:
                pass

        for ph in get_phases_for_mode(mode):
            self._build_agent_row(ph)

    def _build_agent_row(self, ph: dict) -> None:
        row = ctk.CTkFrame(self.agents_scroll,
                           fg_color="transparent",
                           corner_radius=theme.RADIUS_SMALL)
        row.pack(fill="x", pady=1, padx=4)
        row.grid_columnconfigure(1, weight=1)

        dot = status_dot(row, color=theme.TEXT_DIM, size=10)
        dot.grid(row=0, column=0, padx=(8, 10), pady=8)

        # Inline button for the row name so click selects the agent.
        name_btn = ctk.CTkButton(
            row, text=ph["name"], anchor="w", height=30,
            fg_color="transparent",
            text_color=theme.TEXT_SUB,
            hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_SMALL,
            corner_radius=theme.RADIUS_SMALL,
            command=lambda pid=ph["id"]: self._select_agent(pid),
        )
        name_btn.grid(row=0, column=1, sticky="ew")

        extra = ctk.CTkLabel(
            row, text="",
            font=theme.FONT_TINY, text_color=theme.TEXT_DIM,
            anchor="e",
        )
        extra.grid(row=0, column=2, sticky="e", padx=(0, 10))

        # v2.8.0 (Cos audit B-12): typed NamedTuple instead of an
        # anonymous tuple — consistent shape with done.py.
        self._agent_rows[ph["id"]] = AgentRowWidgets(
            row=row, dot=dot, name_btn=name_btn, extra=extra,
            phase_meta=ph,
        )

    def _select_agent(self, pid: str) -> None:
        self.app.app_state.selected_agent = pid
        self._refresh_output()

    def refresh(self) -> None:
        s = self.app.app_state
        total = len(s.current_status)
        done = sum(1 for v in s.current_status.values() if v == "done")
        if total > 0:
            ratio = done / total
            self.progress.set(ratio)
            # v2.6.0: explicit percentage in the label — Cos P5
            # recommendation. Easier to estimate "how far in" than
            # eyeballing the bar fill against the phase count.
            pct = int(round(ratio * 100))
            self.progress_label.configure(
                text=f"Completed {done} / {total} phases  ({pct}%)"
            )

        running_pid = next(
            (pid for pid, st in s.current_status.items() if st == "running"),
            None,
        )

        for pid, w in self._agent_rows.items():
            status = s.current_status.get(pid, "pending")
            color = {
                "done":    theme.ONLINE,
                "running": theme.ACCENT,
                "error":   theme.OFFLINE,
                "pending": theme.TEXT_DIM,
            }.get(status, theme.TEXT_DIM)
            w.dot.configure(fg_color=color)
            w.name_btn.configure(
                text_color=(theme.TEXT if status in ("done", "running")
                            else theme.TEXT_SUB),
            )

            if pid == "judge" and s.current_judge_rounds:
                last = s.current_judge_rounds[-1]
                w.extra.configure(text=f"{last[1]} {last[2]}/100",
                                  text_color=theme.ACCENT_2)
            elif status == "running":
                w.extra.configure(text="running...",
                                  text_color=theme.ACCENT)
            elif status == "done":
                w.extra.configure(text="done", text_color=theme.TEXT_DIM)
            elif status == "error":
                w.extra.configure(text="error", text_color=theme.OFFLINE)
            else:
                w.extra.configure(text="")

            # Active row highlight
            w.row.configure(
                fg_color=(theme.BG_CARD_HOVER if pid == running_pid
                          else "transparent"),
            )

        # Title bar reflects pipeline state. Look up the row by
        # running_pid — DO NOT rely on the for-loop's leftover `pid`
        # variable; if `_agent_rows` is empty it would be undefined
        # (NameError). Also check that the running pid actually has a
        # row, since pipeline_status keys can include phases not in
        # the displayed mode (e.g. revision rounds).
        if running_pid and running_pid in self._agent_rows:
            running_name = self._agent_rows[running_pid].name_btn.cget("text")
            self.title_label.configure(
                text=f"Working on  {running_name}",
                text_color=theme.ACCENT,
            )
            self._running_dot.configure(fg_color=theme.ACCENT)
        else:
            self.title_label.configure(
                text="Team working", text_color=theme.ACCENT,
            )

        # Auto-select latest completed if user hasn't picked.
        if ((not s.selected_agent)
                or s.selected_agent not in s.current_outputs):
            done_ids = [pid for pid in self._agent_rows
                        if s.current_status.get(pid) == "done"
                        and pid in s.current_outputs]
            if done_ids:
                s.selected_agent = done_ids[-1]
        self._refresh_output()

    def _refresh_output(self) -> None:
        s = self.app.app_state
        sel = s.selected_agent
        if sel and sel in s.current_outputs:
            name = (self._agent_rows[sel].name_btn.cget("text")
                    if sel in self._agent_rows else sel)
            self.output_title.configure(text=f"OUTPUT — {name}".upper())
            render_output_to_textbox(self.output_text,
                                      s.current_outputs[sel])
        else:
            self.output_title.configure(
                text="OUTPUT — WAITING FOR FIRST AGENT"
            )
            self.output_text.configure(state="normal")
            self.output_text.delete("1.0", "end")
            self.output_text.insert(
                "end",
                "Waiting for the first agent to finish.\n"
                "Output appears here as soon as a phase completes.",
            )
            self.output_text.configure(state="disabled")

    # ── Stop ─────────────────────────────────────────────────────────────
    def _stop(self) -> None:
        if not messagebox.askyesno(
            "Stop pipeline?",
            "Stop the running pipeline?\n"
            "Output produced so far will be kept.",
        ):
            return
        self.app.stop_pipeline()
        self.stop_btn.configure(state="disabled", text="Stopping...")
