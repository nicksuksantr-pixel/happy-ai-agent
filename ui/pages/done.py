"""Done — completion summary + downloads + Build .exe."""
from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk


# v2.8.0 (Cos audit B-11): atomic write helper for user-facing downloads.
# A crash mid-write must NEVER leave the destination as a truncated file —
# from the user's POV that's "the download silently corrupted my data".
# Pattern: tempfile in the destination dir → fsync → os.replace (atomic
# on the same volume). Identical to core/persistence._atomic_write_text.
def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, content: str) -> None:
    _atomic_write_bytes(path, content.encode("utf-8"))

from agents import get_phases_for_mode
from builder import (
    PYTHON_MISSING_SENTINEL,
    build_exe_from_session,
    install_python_via_winget,
    open_python_org,
)
from extractor import build_full_export_zip, build_zip, extract_from_session
from pipeline import build_combined_txt, delete_session, load_session

from core import config
from ui import theme
from ui.components.agent_row import AgentRowWidgets
from ui.components.output_view import create_output_text, render_output_to_textbox
from ui.components.page_header import page_header
from ui.components.status_dot import status_dot
from ui.modals.dark_modal import dark_modal


class DonePage(ctk.CTkFrame):
    PAGE_ID = "done"

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=22, pady=18)
        outer.grid_columnconfigure(1, weight=1)
        outer.grid_rowconfigure(4, weight=1)

        page_header(outer, title="Result",
                    subtitle="Completed run outputs + exports.",
                    emoji="🎉", row=0)

        # ── Status banner ────────────────────────────────────────────────
        banner = ctk.CTkFrame(
            outer, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DIM, border_width=1,
            corner_radius=theme.RADIUS_CARD,
        )
        banner.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 12))
        banner.grid_columnconfigure(1, weight=1)

        self._banner_dot = status_dot(banner, color=theme.ONLINE, size=14)
        self._banner_dot.grid(row=0, column=0, padx=(16, 12),
                              pady=14, rowspan=2)

        self.title_label = ctk.CTkLabel(
            banner, text="Completed",
            font=theme.FONT_HEADING, text_color=theme.ONLINE, anchor="w",
        )
        self.title_label.grid(row=0, column=1, sticky="ew", pady=(14, 0))

        self.status_label = ctk.CTkLabel(
            banner, text="",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
            anchor="w", wraplength=900, justify="left",
        )
        self.status_label.grid(row=1, column=1, sticky="ew", pady=(0, 14))

        # ── Action strip ─────────────────────────────────────────────────
        actions = ctk.CTkFrame(outer, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        for i in range(4):
            actions.grid_columnconfigure(i, weight=1, uniform="actions")

        self.dl_txt_btn = self._action_button(
            actions, column=0,
            label="Download report\n.txt",
            command=self._download_txt,
        )
        self.dl_code_btn = self._action_button(
            actions, column=1,
            label="Download code\n.zip",
            command=self._download_code,
        )
        self.dl_all_btn = self._action_button(
            actions, column=2,
            label="Download all\n.zip",
            command=self._download_all,
        )
        self.build_exe_btn = ctk.CTkButton(
            actions, text="Build .exe",
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color="white",
            font=theme.FONT_BODY_BOLD,
            height=64, corner_radius=theme.RADIUS_BUTTON,
            command=self._build_exe,
        )
        self.build_exe_btn.grid(row=0, column=3, sticky="ew", padx=(4, 0))

        # ── Two-pane: agent list + output ───────────────────────────────
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

        # ── Bottom actions ──────────────────────────────────────────────
        bottom = ctk.CTkFrame(outer, fg_color="transparent")
        bottom.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        bottom.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            bottom, text="New task",
            fg_color=theme.ACCENT_2, hover_color=theme.ACCENT_2_HOVER,
            text_color="white",
            height=42, font=theme.FONT_BODY_BOLD,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._new_task,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            bottom, text="Delete this session",
            fg_color=theme.BG_CARD_HOVER, text_color=theme.OFFLINE,
            border_width=1, border_color=theme.OFFLINE,
            hover_color="#3a1f1f",
            font=theme.FONT_BODY_BOLD,
            height=42, corner_radius=theme.RADIUS_BUTTON,
            command=self._delete_session,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self._agent_rows: dict = {}
        self._meta: dict = {}

    def _action_button(self, parent, *, column: int, label: str,
                       command) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            parent, text=label,
            fg_color=theme.BG_CARD_HOVER, text_color=theme.TEXT,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BORDER,
            font=theme.FONT_BODY_BOLD,
            height=64, corner_radius=theme.RADIUS_BUTTON,
            command=command,
        )
        btn.grid(row=0, column=column, sticky="ew",
                 padx=(0 if column == 0 else 4,
                       4 if column < 3 else 0))
        return btn

    # ── Lifecycle ────────────────────────────────────────────────────────
    def on_show(self) -> None:
        sp = self.app.app_state.current_session_path
        if not sp:
            self.title_label.configure(
                text="No session selected", text_color=theme.TEXT_DIM,
            )
            self._banner_dot.configure(fg_color=theme.TEXT_DIM)
            return
        try:
            data = load_session(sp)
            self.app.app_state.current_outputs = data["outputs"]
            self._meta = data["meta"]
        except Exception as e:
            messagebox.showerror("Could not load session", str(e))
            return

        status = self._meta.get("status", "unknown")
        if status == "completed":
            self.title_label.configure(
                text="Completed — every phase finished",
                text_color=theme.ONLINE,
            )
            self._banner_dot.configure(fg_color=theme.ONLINE)
        elif status == "stopped":
            self.title_label.configure(
                text="Stopped — partial output kept",
                text_color=theme.WARN,
            )
            self._banner_dot.configure(fg_color=theme.WARN)
        elif status == "failed":
            self.title_label.configure(
                text="Pipeline failed", text_color=theme.OFFLINE,
            )
            self._banner_dot.configure(fg_color=theme.OFFLINE)
        else:
            self.title_label.configure(
                text=f"Status: {status}", text_color=theme.ACCENT_3,
            )
            self._banner_dot.configure(fg_color=theme.ACCENT_3)

        details = []
        details.append(f"Session: {sp.name}")
        if self._meta.get("last_error"):
            details.append(
                f"Error: {self._meta['last_error'][:200]}"
            )
        self.status_label.configure(text="   ·   ".join(details))

        enabled = status == "completed"
        for btn in (self.dl_txt_btn, self.dl_code_btn,
                    self.dl_all_btn, self.build_exe_btn):
            btn.configure(state="normal" if enabled else "disabled")

        self._build_agent_list()
        outputs = self.app.app_state.current_outputs
        if outputs and (
            (not self.app.app_state.selected_agent)
            or self.app.app_state.selected_agent not in outputs
        ):
            mode = self._meta.get("mode", "quick")
            phases = get_phases_for_mode(mode)
            done_ids = [p["id"] for p in phases if p["id"] in outputs]
            if done_ids:
                self.app.app_state.selected_agent = done_ids[-1]
        self._refresh_output()

    # ── Agent list ───────────────────────────────────────────────────────
    def _build_agent_list(self) -> None:
        for child in self.agents_scroll.winfo_children():
            child.destroy()
        self._agent_rows.clear()

        mode = self._meta.get("mode", "quick")
        outputs = self.app.app_state.current_outputs

        for ph in get_phases_for_mode(mode):
            if ph["id"] not in outputs:
                continue
            self._build_agent_row(ph)

        for k in sorted(outputs.keys()):
            if k.startswith("debugger_revision"):
                self._build_agent_row({"id": k, "name": k, "emoji": ""},
                                       is_revision=True)

    def _build_agent_row(self, ph: dict, *, is_revision: bool = False) -> None:
        row = ctk.CTkFrame(self.agents_scroll,
                           fg_color="transparent",
                           corner_radius=theme.RADIUS_SMALL)
        row.pack(fill="x", pady=1, padx=4)
        row.grid_columnconfigure(1, weight=1)

        color = theme.ACCENT_2 if is_revision else theme.ONLINE
        dot = status_dot(row, color=color, size=10)
        dot.grid(row=0, column=0, padx=(8, 10), pady=8)

        name_btn = ctk.CTkButton(
            row, text=ph["name"], anchor="w", height=30,
            fg_color="transparent",
            text_color=theme.TEXT_SUB,
            hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_SMALL,
            corner_radius=theme.RADIUS_SMALL,
            command=lambda pid=ph["id"]: self._select(pid),
        )
        name_btn.grid(row=0, column=1, sticky="ew")

        # v2.8.0 (Cos audit B-12): same NamedTuple as running.py so both
        # pages can share helpers + the shape is greppable.
        self._agent_rows[ph["id"]] = AgentRowWidgets(
            row=row, dot=dot, name_btn=name_btn, phase_meta=ph,
        )

    def _select(self, pid: str) -> None:
        self.app.app_state.selected_agent = pid
        self._refresh_output()

    def _refresh_output(self) -> None:
        s = self.app.app_state
        sel = s.selected_agent
        if sel and sel in s.current_outputs:
            # B-12: attribute access on the typed NamedTuple
            row = self._agent_rows.get(sel)
            name = (row.phase_meta.get("name") if (row and row.phase_meta)
                    else sel)
            self.output_title.configure(text=f"OUTPUT — {name}".upper())
            render_output_to_textbox(self.output_text,
                                      s.current_outputs[sel])
        else:
            self.output_title.configure(
                text="OUTPUT — CLICK AN AGENT ON THE LEFT"
            )
            self.output_text.configure(state="normal")
            self.output_text.delete("1.0", "end")
            self.output_text.configure(state="disabled")

    # ── Downloads ────────────────────────────────────────────────────────
    def _download_txt(self) -> None:
        sp = self.app.app_state.current_session_path
        if not sp:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"happy_report_{sp.name}.txt",
            filetypes=[("Text", "*.txt")],
        )
        if not path:
            return
        try:
            # v2.8.0 (Cos audit B-11): atomic write so a crash/power-loss
            # mid-write leaves either OLD file or NEW, never half.
            _atomic_write_text(Path(path), build_combined_txt(sp))
            messagebox.showinfo("Saved", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def _download_code(self) -> None:
        sp = self.app.app_state.current_session_path
        if not sp:
            return
        try:
            files = extract_from_session(sp)
        except Exception as e:
            messagebox.showerror("Could not extract code", str(e))
            return
        if not files:
            messagebox.showwarning(
                "No code blocks",
                "Did not find any code blocks in the session output.",
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile=f"happy_code_{sp.name}.zip",
            filetypes=[("ZIP", "*.zip")],
        )
        if not path:
            return
        try:
            _atomic_write_bytes(Path(path), build_zip(files))  # B-11
            messagebox.showinfo("Saved", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def _download_all(self) -> None:
        sp = self.app.app_state.current_session_path
        if not sp:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile=f"happy_all_{sp.name}.zip",
            filetypes=[("ZIP", "*.zip")],
        )
        if not path:
            return
        try:
            combined = build_combined_txt(sp)
            _atomic_write_bytes(  # B-11
                Path(path), build_full_export_zip(sp, combined),
            )
            messagebox.showinfo("Saved", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    # ── Build .exe ───────────────────────────────────────────────────────
    def _build_exe(self) -> None:
        sp = self.app.app_state.current_session_path
        if not sp:
            return
        cached = self.app.app_state.exe_built_cache.get(sp.name)
        if cached and cached.get("ok"):
            self._save_exe_from_cache(cached)
            return

        win, body = dark_modal(
            self, title="Building .exe", emoji="🔨",
            width=540, height=200, closable=False,
        )

        ctk.CTkLabel(
            body, text="Bundling your code into a Windows .exe...",
            font=theme.FONT_SUBHEAD, text_color=theme.ACCENT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew",
               pady=(theme.S2, theme.S1))
        msg_label = ctk.CTkLabel(
            body, text="Preparing...",
            font=theme.FONT_SMALL, text_color=theme.TEXT_SUB,
            anchor="w", wraplength=480, justify="left",
        )
        msg_label.grid(row=1, column=0, sticky="ew",
                       pady=(0, theme.S3))
        prog = ctk.CTkProgressBar(
            body, mode="indeterminate",
            progress_color=theme.ACCENT, fg_color=theme.BG_CARD,
            height=8, corner_radius=4,
        )
        prog.grid(row=2, column=0, sticky="ew")
        prog.start()

        result_box: dict = {}
        modal_alive = {"v": True}

        def progress_cb(text: str) -> None:
            # Guard against the worker still calling progress after the
            # modal got destroyed (Tk widget = "invalid command name").
            if not modal_alive["v"]:
                return
            try:
                self.after(0, lambda t=text: (
                    modal_alive["v"] and msg_label.configure(text=t)
                ))
            except Exception:
                pass

        def worker() -> None:
            try:
                ok, msg, b, fname = build_exe_from_session(
                    sp, progress_cb=progress_cb
                )
                result_box.update(
                    ok=ok, message=msg, bytes=b, filename=fname
                )
            except Exception as e:
                result_box.update(
                    ok=False, message=f"Build error: {e}",
                    bytes=None, filename=None,
                )
            self.after(0, _finish)

        def _finish() -> None:
            modal_alive["v"] = False
            try:
                prog.stop()
            except Exception:
                pass
            try:
                win.grab_release()
                win.destroy()
            except Exception:
                pass
            # Defer the re-render of the parent so modal teardown finishes
            # first (playbook Phase 2 pitfall).
            self.app.app_state.exe_built_cache[sp.name] = result_box
            self.after(50, lambda: self._after_build(result_box))

        threading.Thread(target=worker, daemon=True).start()

    def _after_build(self, result_box: dict) -> None:
        if result_box.get("ok"):
            self._save_exe_from_cache(result_box)
            return

        msg = result_box.get("message", "unknown")
        # Special case: builder signalled "Python not installed" — offer
        # to auto-install via winget instead of just dumping an error.
        if msg == PYTHON_MISSING_SENTINEL:
            self._handle_python_missing()
            return
        messagebox.showerror("Build failed", msg)

    def _handle_python_missing(self) -> None:
        """Python isn't installed on this machine. Offer to auto-install
        via winget (~30 MB, 1-2 min). Fall back to opening python.org."""
        if not messagebox.askyesno(
            "Python not installed",
            "Building .exe needs Python on your machine, and we didn't "
            "find it.\n\n"
            "Install Python 3.13 automatically? (about 30 MB, 1-2 minutes)\n\n"
            "Click No to open python.org and install manually instead.",
        ):
            open_python_org()
            messagebox.showinfo(
                "Python download",
                "Browser opened to python.org. After install, come back "
                "and click Build .exe again.",
            )
            return
        self._run_python_install()

    def _run_python_install(self) -> None:
        """Show a modal while winget installs Python. On success, retry
        the Build .exe automatically. On failure, fall back to python.org."""
        from ui.modals.dark_modal import dark_modal as _dark_modal
        win, body = _dark_modal(
            self, title="Installing Python", emoji="🐍",
            width=560, height=200, closable=False,
        )

        ctk.CTkLabel(
            body, text="Installing Python 3.13 via winget...",
            font=theme.FONT_SUBHEAD, text_color=theme.ACCENT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew",
               pady=(theme.S2, theme.S1))
        msg_label = ctk.CTkLabel(
            body, text="Starting...",
            font=theme.FONT_SMALL, text_color=theme.TEXT_SUB,
            anchor="w", wraplength=480, justify="left",
        )
        msg_label.grid(row=1, column=0, sticky="ew", pady=(0, theme.S3))
        prog = ctk.CTkProgressBar(
            body, mode="indeterminate",
            progress_color=theme.ACCENT, fg_color=theme.BG_CARD,
            height=8, corner_radius=4,
        )
        prog.grid(row=2, column=0, sticky="ew")
        prog.start()

        modal_alive = {"v": True}

        def progress_cb(text: str) -> None:
            if not modal_alive["v"]:
                return
            try:
                self.after(0, lambda t=text: (
                    modal_alive["v"] and msg_label.configure(text=t)
                ))
            except Exception:
                pass

        result = {}

        def worker():
            ok, m = install_python_via_winget(progress_cb=progress_cb)
            result["ok"] = ok
            result["msg"] = m
            self.after(0, _finish)

        def _finish():
            modal_alive["v"] = False
            try:
                prog.stop()
                win.grab_release()
                win.destroy()
            except Exception:
                pass
            if result.get("ok"):
                messagebox.showinfo(
                    "Python installed",
                    "Python is ready. Retrying the .exe build now.",
                )
                # Retry build_exe from scratch.
                self.app.app_state.exe_built_cache.pop(
                    self.app.app_state.current_session_path.name, None
                )
                self.after(150, self._build_exe)
            else:
                if messagebox.askyesno(
                    "winget install failed",
                    f"{result.get('msg', 'unknown error')}\n\n"
                    f"Open python.org to install manually?",
                ):
                    open_python_org()

        threading.Thread(target=worker, daemon=True).start()

    def _save_exe_from_cache(self, cached: dict) -> None:
        if not cached.get("bytes"):
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".exe",
            initialfile=cached.get("filename") or "happy_app.exe",
            filetypes=[("Executable", "*.exe")],
        )
        if not path:
            return
        try:
            _atomic_write_bytes(Path(path), cached["bytes"])  # B-11
            messagebox.showinfo(
                "Build successful",
                f"{cached.get('message', '')}\n\nSaved to:\n{path}",
            )
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    # ── Navigation ───────────────────────────────────────────────────────
    def _new_task(self) -> None:
        self.app.app_state.current_session_path = None
        self.app.app_state.current_outputs = {}
        self.app.app_state.current_status = {}
        self.app.app_state.current_judge_rounds = []
        self.app.app_state.selected_agent = None
        self.app.show_page("home")

    def _delete_session(self) -> None:
        sp = self.app.app_state.current_session_path
        if not sp:
            return
        if not messagebox.askyesno(
            "Delete session?", f"Delete '{sp.name}'?"
        ):
            return
        try:
            delete_session(sp)
            self.app.app_state.current_session_path = None
            self.app.app_state.current_outputs = {}
            self.app.show_page("home")
        except Exception as e:
            messagebox.showerror("Could not delete", str(e))
