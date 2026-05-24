"""HappyApp — root window with Phase 3 polish.

Implements the new-desktop-project playbook's "feels like a real app"
checklist:
- Window geometry persistence (debounced save on <Configure>, restore
  on next launch, final save in destroy).
- System tray (pystray) — X button hides to tray; Quit really exits.
- AppState carrying auth + pipeline + settings.
- Pipeline queue drained on the Tk mainloop (workers post events via
  Queue.put; main loop drains every 200 ms).
- Periodic update re-check (initial + hourly).
"""
from __future__ import annotations

import json
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Dict, Optional

import customtkinter as ctk

# Load core first — its import side-effect populates os.environ from
# `.env`, and updater.py reads HAPPY_AI_UPDATE_TOKEN at module import
# time. If updater imports before core, the PAT lookup misses the env.
from core import config
from core.persistence import (
    load_settings,
    load_window_state,
    save_settings,
    save_window_state,
)

from auth import (
    create_client,
    list_available_models,
    load_api_key,
)
from agents import get_phases_for_mode
from file_loader import (
    load_attachments_from_session,
    save_attachments_to_session,
)
from pipeline import (
    AuthError,
    PipelineRunner,
    create_session,
    update_meta,
)
import updater
from ui import theme
from ui.sidebar import Sidebar
from ui.pages.home import HomePage
from ui.pages.runs import RunsPage
from ui.pages.stats import StatsPage
from ui.pages.settings import SettingsPage
from ui.pages.running import RunningPage
from ui.pages.done import DonePage


# ─── AppState ─────────────────────────────────────────────────────────────
class AppState:
    """Mutable application state. Replaces Streamlit's `session_state`.

    All pages read/write through `self.app.app_state`, so page navigation
    doesn't lose anything. Settings persist via `core.persistence`.
    """

    def __init__(self) -> None:
        self.client = None
        self.api_key: str = ""
        self.auth_ready: bool = False
        self.available_models: list[str] = []

        # Settings (merged with DEFAULT_SETTINGS so missing keys fall back).
        s = load_settings()
        self.model: str = s["model"]
        self.delay: int = s["delay"]
        self.judge_threshold: int = s["judge_threshold"]
        self.max_judge_loops: int = s["max_judge_loops"]
        self.pipeline_mode: str = s["pipeline_mode"]
        # v2.7.0: project type selector on Home page.
        # Values: "html" / "desktop_installer" — see
        # `core.config.DEFAULT_SETTINGS` + `agents.PROJECT_TYPE_DIRECTIVES`.
        self.project_type: str = s.get("project_type", "html")

        # Pipeline state.
        self.current_session_path: Optional[Path] = None
        self.current_outputs: Dict[str, str] = {}
        self.current_status: Dict[str, str] = {}
        self.current_judge_rounds: list = []
        self.selected_agent: Optional[str] = None
        self.attached_files: list = []

        self.pipeline_thread: Optional[threading.Thread] = None
        self.pipeline_queue: Optional[queue.Queue] = None
        self.pipeline_runner = None  # PipelineRunner instance (live counters)
        self.stop_flag: Dict[str, bool] = {"stop": False}
        self.started_at: Optional[float] = None
        self.running: bool = False

        self.exe_built_cache: Dict[str, dict] = {}

    def persist(self) -> None:
        save_settings({
            "model": self.model,
            "delay": self.delay,
            "judge_threshold": self.judge_threshold,
            "max_judge_loops": self.max_judge_loops,
            "pipeline_mode": self.pipeline_mode,
            "project_type": self.project_type,
        })

    def auto_auth(self) -> None:
        """Try to authenticate from the saved key on disk.

        Honors format-only validation here for fast startup — the
        EXPENSIVE check (real Gemini API ping) is deferred to
        `verify_auth_with_api`, called from a background thread once
        the UI is up. That way startup stays snappy AND a stale/junk
        key on disk doesn't masquerade as "Connected" forever.
        """
        if self.auth_ready:
            return
        key = load_api_key()
        if not key:
            return
        client, err = create_client(key)
        if err:
            return
        self.client = client
        self.api_key = key
        self.auth_ready = True
        try:
            self.available_models = list_available_models(client) or []
            if (self.available_models
                    and self.model not in self.available_models):
                self.model = self.available_models[0]
                self.persist()
        except Exception:
            pass

    def verify_auth_with_api(self) -> bool:
        """Call Gemini's list_models to confirm the saved key is real.

        Returns True if the key is valid. On failure, wipes the
        client + auth_ready so the UI flips back to "Not connected"
        and the user can paste a fresh key. Designed to be called
        from a worker thread; only state mutation, no widget access.
        """
        if not self.client:
            return False
        try:
            from auth import test_connection
            ok, _msg = test_connection(self.client)
        except Exception:
            ok = False
        if not ok:
            self.client = None
            self.auth_ready = False
        return ok


# ─── Root window ──────────────────────────────────────────────────────────
class HappyApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        # ASCII title — em-dash drops from WM_NAME in some frozen Tcl/Tk
        # builds. Two spaces between name and version reads nicely too.
        self.title(config.APP_TITLE)

        # Restore last geometry BEFORE any other geometry() call. If the
        # saved string is corrupt, fall back to the playbook default.
        saved = load_window_state().get("geometry")
        if saved and isinstance(saved, str):
            try:
                self.geometry(saved)
            except Exception:
                self.geometry(f"{config.WINDOW_W}x{config.WINDOW_H}")
        else:
            self.geometry(f"{config.WINDOW_W}x{config.WINDOW_H}")
        self.minsize(config.MIN_W, config.MIN_H)

        try:
            if config.ICON_PATH.exists():
                self.iconbitmap(default=str(config.ICON_PATH))
        except Exception:
            pass

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=theme.BG_ROOT)

        # current_page MUST exist before Sidebar() — Sidebar.__init__ calls
        # refresh_auth_status() which reads self.app.current_page (lesson
        # from feedback_ctk_parent_attr_before_child_init).
        self.current_page: str = "home"

        # Geometry-persist debounce.
        self._geo_save_id: Optional[str] = None
        self.bind("<Configure>", self._on_window_configure)

        # System tray bookkeeping.
        self._tray_icon = None
        self._tray_thread: Optional[threading.Thread] = None
        self._really_quit: bool = False

        # Updater state.
        # Lifecycle: idle -> detecting -> downloading -> ready -> installing
        # Once "ready", the installer ZIP is on disk under cache_dir() and
        # we just need to spawn it. Install never happens automatically
        # while a pipeline is running — Nick's data-loss directive.
        self._update_info: Optional["updater.UpdateInfo"] = None
        self._update_check_id: Optional[str] = None
        self._update_download_path = None      # Path to the downloaded zip
        self._update_downloading: bool = False  # background download in flight
        self._update_ready: bool = False        # download done, install pending
        self._installing: bool = False          # in launch_installer_and_exit
        self._auto_install_toast_open: bool = False
        # Cancel handle for the in-flight background download. set()
        # in destroy() so the worker exits its read loop quickly
        # instead of holding the daemon thread until Python tears
        # down the interpreter (HPO v1.034 pattern).
        self._update_cancel_event: threading.Event = threading.Event()

        # ── State ───────────────────────────────────────────────────────
        self.app_state = AppState()
        self.app_state.auto_auth()
        # Kick off a background verification — if the saved key is junk
        # (format passes but the API rejects it), this flips auth_ready
        # back to False after a couple of seconds and refreshes the UI
        # pills + Settings status so the user sees the real state.
        self._schedule_auth_verification()

        # ── Layout ──────────────────────────────────────────────────────
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, self)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.main = ctk.CTkFrame(self, fg_color=theme.BG_PAGE)
        self.main.grid(row=0, column=1, sticky="nsew",
                       padx=0, pady=0)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        # ── Pages ───────────────────────────────────────────────────────
        self.pages: Dict[str, ctk.CTkFrame] = {}
        for cls in (HomePage, RunsPage, StatsPage, SettingsPage,
                    RunningPage, DonePage):
            self.pages[cls.PAGE_ID] = cls(self.main, self)

        # Start page priority:
        #   1. HAPPY_START_PAGE env var (QA / debug)
        #   2. last_page from window_state.json (user's last regular page)
        #   3. "home" fallback
        # The QA env var must NOT pollute the persisted preference, so
        # disable last_page persistence for the duration of this initial
        # show_page call.
        import os as _os
        env_start = _os.environ.get("HAPPY_START_PAGE")
        if env_start:
            start = env_start
        else:
            saved = load_window_state().get("last_page")
            start = saved if saved in ("home", "runs", "stats", "settings") else "home"
        start = start.lower()
        if start not in self.pages:
            start = "home"
        self._persisting_last_page = False
        self.show_page(start)
        self._persisting_last_page = True

        # ── Background loops ────────────────────────────────────────────
        # Track the drain ticker's after-id so destroy() can cancel it —
        # stops Tcl warnings about callbacks scheduled on a destroyed
        # widget if the X-button quit beats the next 200 ms tick.
        self._drain_id: Optional[str] = self.after(
            200, self._drain_pipeline_queue
        )
        self.after(3000, self._check_for_update_now)
        self._schedule_next_update_check()

        # ── Tray + close handler ────────────────────────────────────────
        self._setup_tray()
        self.bind("<Unmap>", self._on_unmap)
        self.protocol("WM_DELETE_WINDOW", self._on_user_close)

    # ── Background auth verification ─────────────────────────────────────
    def _schedule_auth_verification(self) -> None:
        """Fire a background API ping shortly after startup. Only runs
        when auto_auth already loaded a key — no point pinging if the
        user hasn't connected. Fast startups feel responsive but a
        junk key still gets caught within seconds."""
        if not self.app_state.auth_ready:
            return

        def worker():
            ok = self.app_state.verify_auth_with_api()
            # State already mutated by verify_auth_with_api on failure;
            # we just need to refresh the UI on the Tk thread. Guard
            # against the app having been destroyed mid-verification
            # (test runs, or user quits within ~1s of launch) — Tk's
            # `after` raises TclError if the widget is already gone.
            try:
                self.after(0, lambda r=ok: self._on_auth_verified(r))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_auth_verified(self, ok: bool) -> None:
        """Tk-thread callback after background API verification."""
        try:
            self.sidebar.refresh_auth_status()
        except Exception:
            pass
        # If the settings page is currently mounted, refresh its
        # status label too so the user immediately sees the change.
        try:
            settings = self.pages.get("settings")
            if settings and hasattr(settings, "_refresh_auth_status"):
                settings._refresh_auth_status()
        except Exception:
            pass

    # ── Window geometry persistence ──────────────────────────────────────
    def _on_window_configure(self, event) -> None:
        if event.widget is not self:
            return  # bubbled from a child widget
        if self._geo_save_id is not None:
            try:
                self.after_cancel(self._geo_save_id)
            except Exception:
                pass
        # 600 ms debounce — <Configure> fires dozens of times per drag.
        self._geo_save_id = self.after(600, self._persist_geometry)

    def _persist_geometry(self) -> None:
        try:
            # Guard against persisting geometry while the window is
            # withdrawn (hide-to-tray) or iconified — Tk reports a
            # nonsense "1x1+0+0" or stale pre-hide value in those
            # states, which on next launch would either snap the
            # window into a 1x1 pixel postage stamp or load a
            # phantom previous-position. HPO v1.034 pattern.
            try:
                wstate = self.state()
            except Exception:
                wstate = "normal"
            if wstate in ("withdrawn", "iconic"):
                self._geo_save_id = None
                return
            geo = self.geometry()
            # Bonus sanity: a freshly-restored window can briefly
            # report "1x1+0+0" before Tk computes the real bbox.
            # Never persist that.
            if geo.startswith("1x1"):
                self._geo_save_id = None
                return
            # Merge so we don't clobber other keys (e.g. last_page).
            state = load_window_state()
            state["geometry"] = geo
            save_window_state(state)
        except Exception:
            pass
        self._geo_save_id = None

    def _persist_last_page(self, page_id: str) -> None:
        """Remember which page the user last visited so reopening lands
        there. Pipeline-bound pages (running/done) aren't persisted —
        those are session-specific. The QA `HAPPY_START_PAGE` env var
        also flips `_persisting_last_page = False` during __init__ so
        debug runs don't overwrite the real preference."""
        if not getattr(self, "_persisting_last_page", True):
            return
        if page_id in ("running", "done"):
            return
        try:
            state = load_window_state()
            state["last_page"] = page_id
            save_window_state(state)
        except Exception:
            pass

    # ── System tray ──────────────────────────────────────────────────────
    def _setup_tray(self) -> None:
        try:
            import pystray
            from PIL import Image as _PILImage
        except Exception:
            return
        if not config.ICON_PATH.exists():
            return
        try:
            image = _PILImage.open(str(config.ICON_PATH))
        except Exception:
            return

        menu = pystray.Menu(
            pystray.MenuItem("Show", self._tray_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._tray_quit),
        )
        try:
            self._tray_icon = pystray.Icon(
                "happy-ai-agent", image, config.TRAY_TOOLTIP, menu,
            )
            self._tray_thread = threading.Thread(
                target=self._tray_icon.run, daemon=True
            )
            self._tray_thread.start()
        except Exception:
            self._tray_icon = None

    def _tray_show(self, icon=None, item=None) -> None:
        self.after(0, self._do_show)

    def _tray_quit(self, icon=None, item=None) -> None:
        self.after(0, self._do_real_quit)

    def _do_show(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _do_real_quit(self) -> None:
        """Tray Quit. Warn if a pipeline is mid-run (would lose work)."""
        if self.app_state.running:
            if not messagebox.askyesno(
                "Pipeline running",
                "A pipeline is still running.\n\n"
                "Quitting now will lose the in-progress run.\n"
                "Continue?",
            ):
                # User changed their mind — bring window back so they
                # can see the running pipeline + stop it cleanly.
                #
                # CRITICAL: reset `_really_quit` to False here. The
                # tray-failure fallback in `_on_user_close` flips it to
                # True *before* calling us; if we leave it set, the
                # next X-button press would silently destroy without
                # the warning dialog — i.e. lose work after the user
                # explicitly said "don't quit". Same applies to the
                # tray-Quit menu re-click after a reject.
                self._really_quit = False
                try:
                    self.deiconify()
                    self.lift()
                except Exception:
                    pass
                return
            self.app_state.stop_flag["stop"] = True
        self._really_quit = True
        # If an update is downloaded + nothing's running, apply it on
        # quit instead of just exiting — Nick's auto-install rule.
        if (self._update_ready and not self.app_state.running
                and not self._installing):
            try:
                self._apply_update_now()
                return  # sys.exit() inside _apply_update_now
            except SystemExit:
                raise
            except Exception:
                pass
        if self._tray_icon is not None:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        self.destroy()

    def _on_user_close(self) -> None:
        """X button: hide to tray unless Quit was invoked.

        If a pipeline is mid-run, warn the user before quitting — closing
        the window doesn't lose work (tray keeps the run alive), but
        explicit Quit would. _do_real_quit handles the Quit branch with
        its own warning + state-save path; here we just hide to tray.

        Tray-failure fallback (ENA Desktop v2.6.6 pattern): if pystray
        failed to start (`_tray_icon is None`), hiding to tray would
        strand the user — no taskbar entry, no tray icon, no way back.
        In that case fall through to a real quit so X behaves like Quit.
        """
        if self._really_quit:
            self.destroy()
            return
        if self._tray_icon is None:
            # No tray available — withdraw would orphan the user. Treat
            # X as Quit (with the same data-loss guard as _do_real_quit).
            self._really_quit = True
            self._do_real_quit()
            return
        self.withdraw()

    def _on_unmap(self, event) -> None:
        """Convert minimize -> withdraw so the window leaves the taskbar."""
        if event.widget is not self:
            return
        try:
            state = self.state()
        except Exception:
            return
        if state == "iconic":
            self.after(50, self.withdraw)

    # ── Update-check plumbing ────────────────────────────────────────────
    def _check_for_update_now(self) -> None:
        def worker():
            try:
                info = updater.check_for_update(
                    config.VERSION, timeout=4.0
                )
            except Exception:
                info = None
            if info:
                self.after(0, lambda i=info: self._on_update_found(i))

        threading.Thread(target=worker, daemon=True).start()

    def _schedule_next_update_check(self) -> None:
        if self._update_check_id is not None:
            try:
                self.after_cancel(self._update_check_id)
            except Exception:
                pass
        self._update_check_id = self.after(
            config.UPDATE_CHECK_MS, self._periodic_update_check
        )

    def _periodic_update_check(self) -> None:
        self._check_for_update_now()
        self._schedule_next_update_check()

    def _on_update_found(self, info) -> None:
        """A newer release is available. Start a SILENT background download
        immediately — Nick's directive: "อัพเดทออโตแบบทำงานเบื้องหลังเงียบๆ".
        When the download finishes the sidebar pill flips to "ready — click
        to apply".

        If a pipeline is currently running, the download still proceeds
        (it's bandwidth only) but install is deferred until the run ends.
        """
        # Already known? Don't restart the download.
        if self._update_info and self._update_info.tag == info.tag:
            if self._update_ready or self._update_downloading:
                return
        self._update_info = info

        # Sidebar pill — initial "downloading" state.
        try:
            self.sidebar.show_update_pill(info, state="downloading")
        except Exception:
            pass

        self._start_background_download(info)

    def _start_background_download(self, info) -> None:
        """Fire-and-forget download under cache_dir()/installer.zip.

        Caller is responsible for updating the pill. Worker thread posts
        completion via after() so widget updates stay on the Tk loop.
        """
        if self._update_downloading:
            return
        self._update_downloading = True
        # Fresh event per download so a previously-cancelled run doesn't
        # abort this one before the first byte. The destroy() path will
        # set whichever instance is current.
        self._update_cancel_event = threading.Event()
        dest = updater.cache_dir() / updater.INSTALLER_ASSET_NAME
        cancel_event = self._update_cancel_event

        def worker():
            ok, _msg = updater.download_installer(
                info.download_url, dest,
                progress_cb=None,        # silent
                cancel_event=cancel_event,
            )
            # If we got cancelled (e.g. user quit mid-download) don't
            # bother posting back to the destroyed widget — the Tk
            # mainloop has already exited.
            if cancel_event.is_set():
                return
            self.after(0, lambda: self._finish_background_download(
                ok=ok, dest=dest, info=info
            ))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_background_download(self, *, ok: bool, dest, info) -> None:
        self._update_downloading = False
        if not ok:
            # Don't pop a modal — quietly drop. Periodic re-check will
            # retry within an hour.
            try:
                self.sidebar.hide_update_pill()
            except Exception:
                pass
            return
        self._update_download_path = dest
        self._update_ready = True
        # Prune older cached installers (.zip + extracted folders) —
        # keep only the file we just downloaded. Without this, every
        # release would accumulate ~91 MB in ~/.happy/updates/ forever.
        try:
            updater.cleanup_old_installers(keep=dest.name)
        except Exception:
            pass
        try:
            self.sidebar.show_update_pill(info, state="ready")
        except Exception:
            pass
        # Nick's directive: auto-install — don't make the user click a
        # button. Schedule the countdown immediately; it will defer
        # itself if a pipeline is running or another modal is open.
        self._schedule_auto_install()

    def offer_install_update(self) -> None:
        """User clicked the sidebar update pill. Behaviour depends on
        state + pipeline activity."""
        info = self._update_info
        if not info:
            return

        # GUARD: never install while a pipeline is running — Nick's
        # data-loss directive. The pill stays visible; we just warn.
        if self.app_state.running:
            messagebox.showinfo(
                "Pipeline running",
                f"Update v{info.version} is queued.\n\n"
                f"It will install after the current pipeline finishes — "
                f"updating now would lose the in-progress run.",
            )
            return

        if not self._update_ready:
            # Still downloading. Tell the user to wait.
            if self._update_downloading:
                messagebox.showinfo(
                    "Downloading update",
                    f"v{info.version} is still downloading in the background.\n"
                    f"The pill will turn green when it's ready.",
                )
            else:
                # Edge case: download failed silently — try again.
                self._start_background_download(info)
                try:
                    self.sidebar.show_update_pill(info, state="downloading")
                except Exception:
                    pass
            return

        # Sidebar pill is now an "install now" trigger (skips the
        # countdown toast). No confirm dialog — Nick's directive is
        # zero-click auto-update.
        self._apply_update_now()

    def _maybe_apply_queued_update(self) -> None:
        """Pipeline finished. If an update is queued, kick off the auto
        countdown — the user doesn't have to click anything."""
        if not (self._update_ready and self._update_info):
            return
        try:
            self.sidebar.show_update_pill(
                self._update_info, state="ready"
            )
        except Exception:
            pass
        # Defer a beat so the Done page renders + the user sees pipeline
        # actually finished before the toast appears.
        self.after(2000, self._schedule_auto_install)

    def _schedule_auto_install(self) -> None:
        """Show a non-modal countdown toast, then auto-install when it
        reaches zero. Bail if pipeline is running (will retry when
        pipeline ends via _maybe_apply_queued_update).

        Nick's directive: auto-install — no click required. The toast
        is just a courtesy so the user can save in-progress typing if
        they need to.
        """
        if not (self._update_ready and self._update_info):
            return
        if self.app_state.running:
            return  # try again when pipeline ends
        # Don't stack toasts.
        if getattr(self, "_auto_install_toast_open", False):
            return
        self._auto_install_toast_open = True
        self._show_auto_install_countdown(self._update_info)

    def _show_auto_install_countdown(self, info, seconds: int = 10) -> None:
        """Bottom-right toast with countdown + Skip. Auto-installs on 0."""
        toast = ctk.CTkToplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=theme.BG_CARD)

        # Bottom-right of the main window. Clamp to the primary screen
        # so multi-monitor layouts with negative coords don't push the
        # toast off-screen.
        TOAST_W, TOAST_H = 340, 100
        MARGIN = 20
        try:
            self.update_idletasks()
            x = self.winfo_rootx() + self.winfo_width() - TOAST_W - MARGIN
            y = self.winfo_rooty() + self.winfo_height() - TOAST_H - MARGIN
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = max(0, min(x, sw - TOAST_W - MARGIN))
            y = max(0, min(y, sh - TOAST_H - MARGIN))
            toast.geometry(f"{TOAST_W}x{TOAST_H}+{x}+{y}")
        except Exception:
            toast.geometry(f"{TOAST_W}x{TOAST_H}+200+200")

        shell = ctk.CTkFrame(
            toast, fg_color=theme.BG_CARD,
            border_color=theme.SUCCESS, border_width=2,
            corner_radius=theme.RADIUS_CARD,
        )
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            shell,
            text=f"Update v{info.version} ready",
            font=theme.FONT_BODY_BOLD, text_color=theme.SUCCESS,
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="ew",
                   padx=theme.S3, pady=(theme.S3, 0))

        msg_label = ctk.CTkLabel(
            shell,
            text=f"Installing in {seconds} sec...",
            font=theme.FONT_SMALL, text_color=theme.TEXT_SUB,
            anchor="w",
        )
        msg_label.grid(row=1, column=0, sticky="ew",
                       padx=theme.S3, pady=(0, theme.S1))

        btn_row = ctk.CTkFrame(shell, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew",
                     padx=theme.S3, pady=(0, theme.S2))
        btn_row.grid_columnconfigure(0, weight=1)

        # Local state container — countdown method + click handlers mutate.
        state = {"remaining": seconds, "cancel": False, "tick_id": None,
                 "alive": True}

        def do_skip():
            state["cancel"] = True
            state["alive"] = False
            try:
                if state["tick_id"]:
                    self.after_cancel(state["tick_id"])
            except Exception:
                pass
            try:
                toast.destroy()
            except Exception:
                pass
            self._auto_install_toast_open = False

        def do_now():
            state["cancel"] = True
            state["alive"] = False
            try:
                if state["tick_id"]:
                    self.after_cancel(state["tick_id"])
            except Exception:
                pass
            try:
                toast.destroy()
            except Exception:
                pass
            self._auto_install_toast_open = False
            self._apply_update_now()

        ctk.CTkButton(
            btn_row, text="Install now",
            fg_color=theme.SUCCESS, hover_color="#16a34a",
            text_color="white",
            font=theme.FONT_TINY, height=28, width=110,
            corner_radius=theme.RADIUS_BUTTON,
            command=do_now,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            btn_row, text="Skip",
            fg_color="transparent", text_color=theme.TEXT_DIM,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BG_CARD_HOVER,
            font=theme.FONT_TINY, height=28, width=70,
            corner_radius=theme.RADIUS_BUTTON,
            command=do_skip,
        ).grid(row=0, column=1, sticky="e")

        def tick():
            if not state["alive"]:
                return
            # Re-check: pipeline might have started while we were
            # counting down. Bail and let the post-pipeline hook
            # re-schedule the countdown.
            if self.app_state.running:
                do_skip()
                return
            state["remaining"] -= 1
            if state["remaining"] <= 0:
                state["alive"] = False
                try:
                    toast.destroy()
                except Exception:
                    pass
                self._auto_install_toast_open = False
                self._apply_update_now()
                return
            try:
                msg_label.configure(
                    text=f"Installing in {state['remaining']} sec..."
                )
            except Exception:
                pass
            state["tick_id"] = self.after(1000, tick)

        state["tick_id"] = self.after(1000, tick)

    def _apply_update_now(self) -> None:
        """Spawn the installer + exit. Idempotent guard against double
        calls (sidebar pill click + auto-toast firing back-to-back)."""
        if self._installing:
            return
        path = self._update_download_path
        if not path or not path.exists():
            messagebox.showerror(
                "Update missing",
                "The downloaded installer is gone. Try Check for updates.",
            )
            return
        self._installing = True
        try:
            # Save state aggressively before the installer kills us.
            try:
                self.app_state.persist()
                self._persist_geometry()
            except Exception:
                pass
            updater.launch_installer_and_exit(path, silent=True)
        except SystemExit:
            raise
        except Exception as e:
            self._installing = False
            messagebox.showerror("Install failed", str(e)[:200])

    # ── Page navigation ──────────────────────────────────────────────────
    def show_page(self, page_id: str) -> None:
        for frame in self.pages.values():
            frame.grid_forget()
        page = self.pages[page_id]
        page.grid(row=0, column=0, sticky="nsew")
        self.current_page = page_id
        if hasattr(page, "on_show"):
            page.on_show()
        self.sidebar.refresh_history()
        self.sidebar.refresh_auth_status()
        self._persist_last_page(page_id)

    # ── Pipeline lifecycle ───────────────────────────────────────────────
    def start_pipeline(self, task: str, settings: dict) -> None:
        session_path = create_session(task, self.app_state.model, settings)
        if self.app_state.attached_files:
            save_attachments_to_session(
                session_path, self.app_state.attached_files
            )
            update_meta(session_path, has_attachments=True)

        self.app_state.current_session_path = session_path
        self.app_state.current_outputs = {}
        phases = get_phases_for_mode(settings.get("mode", "quick"))
        self.app_state.current_status = {
            p["id"]: "pending" for p in phases
        }
        self.app_state.current_judge_rounds = []
        self.app_state.selected_agent = None
        self.app_state.started_at = time.time()
        self.app_state.running = True
        self.app_state.stop_flag = {"stop": False}
        self.app_state.pipeline_queue = queue.Queue()
        self.app_state.exe_built_cache.pop(session_path.name, None)

        attachments = load_attachments_from_session(session_path)
        q = self.app_state.pipeline_queue
        stop_flag = self.app_state.stop_flag

        def on_start(pid, name, idx):
            q.put(("start", pid, name, idx))

        def on_complete(pid, name, idx, output):
            q.put(("complete", pid, name, idx, output))

        def on_error(pid, name, err):
            q.put(("error", pid, name, err))

        def on_judge(round_num, decision, score):
            q.put(("judge", round_num, decision, score))

        # Build the runner OUTSIDE the worker thread so the Running page
        # can read live counters (runner._tpm, runner.token_log).
        # v2.5.0: pass `get_model` instead of a frozen `model=` so each
        # API call inside the runner resolves the user's CURRENT pick.
        # Without this, the Settings dropdown looked changeable mid-run
        # but the runner kept calling the originally-selected model
        # for the rest of the pipeline. (Settings page already persists
        # `app_state.model` on each dropdown change.)
        # v2.7.0: pass `project_type` so every agent in build_context
        # sees the directive locking deliverable shape (html vs
        # desktop_installer). The project type is captured at pipeline
        # START — switching mid-run would change the deliverable spec
        # halfway through and produce a garbled mix, so we deliberately
        # snapshot it (unlike `model` which is live).
        runner = PipelineRunner(
            client=self.app_state.client,
            get_model=lambda: self.app_state.model,
            delay=settings["delay"],
            judge_threshold=settings["judge_threshold"],
            max_judge_loops=settings["max_judge_loops"],
            mode=settings["mode"],
            attachments=attachments,
            project_type=settings.get("project_type", "html"),
            on_phase_start=on_start,
            on_phase_complete=on_complete,
            on_phase_error=on_error,
            on_judge_round=on_judge,
            should_stop=lambda: stop_flag.get("stop", False),
        )
        self.app_state.pipeline_runner = runner

        def worker():
            try:
                runner.run(task, session_path)
                if stop_flag.get("stop"):
                    try:
                        update_meta(
                            session_path,
                            status="stopped",
                            stopped_at=datetime.now().isoformat(),
                            stopped_by_user=True,
                        )
                    except Exception:
                        pass
                    q.put(("stopped",))
                else:
                    q.put(("done",))
            except AuthError as ae:
                # v2.6.0: 401/PERMISSION_DENIED from Gemini — distinct
                # signal from generic fatal. UI shows a re-auth modal
                # + navigates to Settings instead of dumping a stack
                # trace in a generic "Pipeline error" box.
                try:
                    update_meta(
                        session_path,
                        status="auth_failed",
                        failed_at=datetime.now().isoformat(),
                        last_error=str(ae)[:300],
                    )
                except Exception:
                    pass
                q.put(("auth_error", str(ae)[:300]))
            except Exception as e:
                try:
                    update_meta(
                        session_path,
                        status="failed",
                        failed_at=datetime.now().isoformat(),
                        last_error=str(e)[:300],
                    )
                except Exception:
                    pass
                q.put(("fatal", str(e)[:300]))

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.app_state.pipeline_thread = t

        # If an update is queued, flip the pill text so the user sees
        # "update will install after this run" while the pipeline is
        # working.
        if self._update_ready and self._update_info:
            try:
                self.sidebar.show_update_pill(
                    self._update_info, state="queued"
                )
            except Exception:
                pass

        self.show_page("running")

    def stop_pipeline(self) -> None:
        if (self.app_state.pipeline_thread
                and self.app_state.pipeline_thread.is_alive()):
            self.app_state.stop_flag["stop"] = True

    def _drain_pipeline_queue(self) -> None:
        q = self.app_state.pipeline_queue
        if q is not None:
            try:
                while True:
                    msg = q.get_nowait()
                    self._handle_pipeline_msg(msg)
            except queue.Empty:
                pass
        self._drain_id = self.after(200, self._drain_pipeline_queue)

    def _handle_pipeline_msg(self, msg) -> None:
        kind = msg[0]
        if kind == "start":
            _, pid, *_ = msg
            self.app_state.current_status[pid] = "running"
        elif kind == "complete":
            _, pid, _, _, output = msg
            self.app_state.current_status[pid] = "done"
            self.app_state.current_outputs[pid] = output
        elif kind == "error":
            _, pid, *_ = msg
            self.app_state.current_status[pid] = "error"
        elif kind == "judge":
            _, round_num, decision, score = msg
            self.app_state.current_judge_rounds.append(
                (round_num, decision, score)
            )
        elif kind in ("done", "stopped"):
            self.app_state.running = False
            self.app_state.pipeline_queue = None
            self.app_state.pipeline_runner = None  # release ref for GC
            self.show_page("done")
            self._maybe_apply_queued_update()
            return
        elif kind == "fatal":
            self.app_state.running = False
            self.app_state.pipeline_queue = None
            self.app_state.pipeline_runner = None
            messagebox.showerror(
                "Pipeline error",
                f"The pipeline failed:\n{msg[1]}",
            )
            self.show_page("done")
            self._maybe_apply_queued_update()
            return
        elif kind == "auth_error":
            # v2.6.0: Gemini 401/PERMISSION_DENIED/API_KEY_INVALID.
            # Distinct from generic fatal: the user can fix this by
            # pasting a fresh key, so route them straight to Settings
            # with a clear modal instead of dumping the raw error in
            # the generic "Pipeline error" box.
            self.app_state.running = False
            self.app_state.pipeline_queue = None
            self.app_state.pipeline_runner = None
            # Flip auth_ready so the sidebar pill + Settings card both
            # re-render in "Not connected" state — the saved key is no
            # longer usable, no point pretending it is.
            self.app_state.auth_ready = False
            try:
                self.sidebar.refresh_auth_status()
            except Exception:
                pass
            messagebox.showerror(
                "Gemini auth failed",
                f"Your API key was rejected by Gemini:\n\n{msg[1]}\n\n"
                f"This usually means the key was revoked, expired, or "
                f"the wrong key was saved. Paste a fresh key in Settings "
                f"to re-authenticate.",
            )
            self.show_page("settings")
            return

        if self.current_page == "running":
            self.pages["running"].refresh()

    # ── Shutdown ─────────────────────────────────────────────────────────
    def destroy(self) -> None:
        # Final geometry save in case close beats the debounce.
        try:
            self._persist_geometry()
        except Exception:
            pass
        if self._geo_save_id is not None:
            try:
                self.after_cancel(self._geo_save_id)
            except Exception:
                pass
        if self._update_check_id is not None:
            try:
                self.after_cancel(self._update_check_id)
            except Exception:
                pass
        # Cancel the pipeline-queue drain ticker so the next 200 ms
        # tick doesn't fire on a destroyed widget (raises a Tcl error
        # on some Tk builds).
        if getattr(self, "_drain_id", None) is not None:
            try:
                self.after_cancel(self._drain_id)
            except Exception:
                pass
            self._drain_id = None
        # Signal the background download worker (if any) to abort —
        # the worker checks cancel_event.is_set() inside its read
        # loop and unlinks the partial file before returning. Without
        # this the daemon thread would hold the socket open until
        # Python tears down the interpreter, which can leave a
        # half-written installer in ~/.happy/updates/.
        if getattr(self, "_update_cancel_event", None) is not None:
            try:
                self._update_cancel_event.set()
            except Exception:
                pass
        if self.app_state.running:
            self.app_state.stop_flag["stop"] = True
        try:
            self.app_state.persist()
        except Exception:
            pass
        if self._tray_icon is not None:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        super().destroy()


def main() -> None:
    """Entry point — wired up by happy_native.py at the project root."""
    app = HappyApp()
    app.mainloop()
