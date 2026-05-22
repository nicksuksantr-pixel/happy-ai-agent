"""
happy_native.py — Happy AI Agent (native desktop, no web server, no port collision)

Replaces app.py (Streamlit) + happy_desktop.py (pywebview).
Uses CustomTkinter for native desktop rendering — no HTTP server, no localhost port.

Run dev:  python happy_native.py
Build:    pyinstaller HappyAIAgent.spec
"""
import json
import queue
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image

from pygments import lex
from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
from pygments.token import Token
from pygments.util import ClassNotFound

from auth import (
    create_client, test_connection, list_available_models,
    save_api_key, load_api_key, clear_api_key, is_valid_key_format,
)
from agents import get_phases_for_mode
from file_loader import is_supported, save_attachments_to_session, load_attachments_from_session
from pipeline import (
    PipelineRunner, create_session, update_meta,
    list_sessions, load_session, delete_session, build_combined_txt,
)
from extractor import extract_from_session, build_zip, build_full_export_zip
from builder import build_exe_from_session
import updater


def _read_version() -> str:
    """Single source of truth for the version string. Both source mode and a
    PyInstaller frozen bundle read from a plain-text VERSION file at the project
    root (or _MEIPASS root inside the bundle)."""
    candidates = []
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        candidates.append(Path(mp) / "VERSION")
    candidates.append(Path(__file__).resolve().parent / "VERSION")
    for p in candidates:
        try:
            if p.exists():
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v
        except Exception:
            pass
    return "0.0.0"


VERSION = _read_version()

# Brand palette — full vibrant set
HAPPY_ORANGE = "#FB923C"
HAPPY_ORANGE_DEEP = "#F97316"   # one shade darker for hover/accent
HAPPY_PINK = "#EC4899"
HAPPY_PINK_DEEP = "#DB2777"
HAPPY_YELLOW = "#FBBF24"
HAPPY_PURPLE = "#A855F7"
HAPPY_RED = "#EF4444"
HAPPY_BG = "#FFFBEB"            # warm cream-yellow page bg
HAPPY_SIDEBAR_BG = "#FFF7ED"    # peachy sidebar
HAPPY_TEXT = "#1F2937"
HAPPY_MUTED = "#6B7280"
HAPPY_BORDER = "#FED7AA"
GREEN = "#16A34A"
RED = "#DC2626"

# Light tints used as card backgrounds
TINT_ORANGE = "#FFEDD5"
TINT_PINK = "#FCE7F3"
TINT_YELLOW = "#FEF3C7"
TINT_PURPLE = "#F3E8FF"
TINT_GREEN = "#DCFCE7"
TINT_BLUE = "#DBEAFE"

HERE = Path(__file__).resolve().parent
ASSETS_DIR = HERE / "assets"
ICON_PATH = ASSETS_DIR / "happy_logo.ico"
LOGO_PNG = ASSETS_DIR / "happy_logo.png"
SETTINGS_FILE = Path.home() / ".happy" / "settings.json"


def load_logo_image(target_width: int = 180):
    """Load happy_logo.png as a CTkImage scaled to target_width, preserving aspect.
    Returns None if image missing or PIL fails."""
    try:
        if not LOGO_PNG.exists():
            return None
        img = Image.open(LOGO_PNG)
        w, h = img.size
        new_h = max(1, int(round(target_width * h / w)))
        return ctk.CTkImage(light_image=img, dark_image=img,
                              size=(target_width, new_h))
    except Exception:
        return None


# ─── Gradient button helper (signature orange→pink look) ─────────────────────
_GRADIENT_IMAGE_CACHE: Dict[tuple, "ctk.CTkImage"] = {}


def _make_gradient_image(width: int, height: int,
                            color1_hex: str, color2_hex: str,
                            radius: int = 14):
    """Render a horizontal gradient with rounded corners as a CTkImage.
    Cached by (w,h,c1,c2,r) so repeat buttons reuse the same render."""
    cache_key = (width, height, color1_hex, color2_hex, radius)
    if cache_key in _GRADIENT_IMAGE_CACHE:
        return _GRADIENT_IMAGE_CACHE[cache_key]

    from PIL import Image, ImageDraw
    r1, g1, b1 = int(color1_hex[1:3], 16), int(color1_hex[3:5], 16), int(color1_hex[5:7], 16)
    r2, g2, b2 = int(color2_hex[1:3], 16), int(color2_hex[3:5], 16), int(color2_hex[5:7], 16)

    grad = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(grad)
    for x in range(width):
        ratio = x / max(1, width - 1)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        draw.line([(x, 0), (x, height)], fill=(r, g, b, 255))

    # Apply rounded mask
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height),
                                              radius=radius, fill=255)
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)

    img = ctk.CTkImage(light_image=out, dark_image=out, size=(width, height))
    _GRADIENT_IMAGE_CACHE[cache_key] = img
    return img


def make_gradient_button(parent, text: str, command,
                            color1: str = None, color2: str = None,
                            width: int = 1400, height: int = 56,
                            font=None, radius: int = 28,
                            text_color: str = "white"):
    """Create a CTkButton with a baked-in orange→pink gradient PNG background.

    The signature CTA look from Streamlit v1.032. Because Tkinter has no native
    gradient, we render the gradient with PIL at `width` × `height` and pass it
    as the button image (`compound='center'`) so text overlays the gradient.

    Use `width` >= expected stretched width (e.g., 1400) so the gradient covers
    the button when it expands via `sticky='ew'`.
    """
    c1 = color1 or HAPPY_ORANGE
    c2 = color2 or HAPPY_PINK
    grad = _make_gradient_image(width, height, c1, c2, radius=radius)
    fnt = font or ("Segoe UI", 14, "bold")
    # NOTE: hover_color cannot be 'transparent' (CTk forbids it), but since the
    # gradient image fully covers the fg_color, hover_color is never seen — any
    # valid color works. Using the deeper orange keeps it consistent.
    btn = ctk.CTkButton(
        parent, text=text, image=grad, compound="center",
        text_color=text_color, font=fnt,
        fg_color="transparent", hover_color=HAPPY_ORANGE_DEEP,
        border_width=0, corner_radius=0, height=height,
        anchor="center",
        command=command,
    )
    btn._gradient_image = grad  # prevent GC
    return btn

DEFAULTS = {
    "model": "gemini-3.1-flash-lite-preview",
    "delay": 45,
    "judge_threshold": 100,
    "max_judge_loops": 5,
    "pipeline_mode": "quick",
}


# ─── App state (replaces st.session_state) ───────────────────────────────────
class AppState:
    def __init__(self):
        self.client = None
        self.api_key = ""
        self.auth_ready = False
        self.available_models = []

        for k, v in DEFAULTS.items():
            setattr(self, k, v)
        self.load_settings()

        self.current_session_path: Optional[Path] = None
        self.current_outputs: Dict[str, str] = {}
        self.current_status: Dict[str, str] = {}
        self.current_judge_rounds = []
        self.selected_agent: Optional[str] = None
        self.attached_files = []

        self.pipeline_thread: Optional[threading.Thread] = None
        self.pipeline_queue: Optional[queue.Queue] = None
        self.stop_flag = {"stop": False}
        self.started_at: Optional[float] = None
        self.running = False

        self.exe_built_cache: Dict[str, dict] = {}

    def load_settings(self):
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                for k in DEFAULTS:
                    if k in data:
                        setattr(self, k, data[k])
        except Exception:
            pass

    def save_settings(self):
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {k: getattr(self, k) for k in DEFAULTS}
            SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def auto_auth(self):
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
            if self.available_models and self.model not in self.available_models:
                self.model = self.available_models[0]
                self.save_settings()
        except Exception:
            pass


# ─── Pygments → tk.Text tag rendering ────────────────────────────────────────
PYGMENTS_COLORS = {
    Token.Keyword: "#0033B3",
    Token.Keyword.Constant: "#0033B3",
    Token.Keyword.Declaration: "#0033B3",
    Token.Keyword.Namespace: "#0033B3",
    Token.Name.Class: "#22863A",
    Token.Name.Function: "#6F42C1",
    Token.Name.Decorator: "#6F42C1",
    Token.Name.Builtin: "#005CC5",
    Token.Name.Builtin.Pseudo: "#005CC5",
    Token.Literal.String: "#067D17",
    Token.Literal.String.Doc: "#067D17",
    Token.Literal.Number: "#1750EB",
    Token.Comment: "#8C8C8C",
    Token.Comment.Single: "#8C8C8C",
    Token.Operator: "#000000",
    Token.Punctuation: "#000000",
    Token.Generic.Heading: "#1F2937",
}
_PYG_KEYS = list(PYGMENTS_COLORS.keys())


def _configure_code_tags(text_widget: tk.Text):
    for tok, color in PYGMENTS_COLORS.items():
        text_widget.tag_configure(str(tok), foreground=color)


def _insert_highlighted_code(text_widget: tk.Text, code: str, lang_hint: str = ""):
    try:
        lexer = get_lexer_by_name(lang_hint) if lang_hint else TextLexer()
    except ClassNotFound:
        try:
            lexer = guess_lexer(code)
        except Exception:
            lexer = TextLexer()
    try:
        tokens = list(lex(code, lexer))
    except Exception:
        tokens = [(Token.Text, code)]
    for tok_type, val in tokens:
        # walk up token tree until we find a configured tag
        tt = tok_type
        tag = None
        while tt is not None:
            if tt in PYGMENTS_COLORS:
                tag = str(tt)
                break
            tt = getattr(tt, "parent", None)
        if tag:
            text_widget.insert("end", val, tag)
        else:
            text_widget.insert("end", val)


def render_output_to_textbox(textbox: tk.Text, content: str):
    """Render agent markdown output: headers bold, code blocks highlighted, inline code."""
    import re
    textbox.configure(state="normal")
    textbox.delete("1.0", "end")
    _configure_code_tags(textbox)
    textbox.tag_configure("h1", font=("Segoe UI", 14, "bold"),
                           foreground=HAPPY_ORANGE, spacing1=8, spacing3=4)
    textbox.tag_configure("h2", font=("Segoe UI", 12, "bold"),
                           foreground=HAPPY_PINK, spacing1=6, spacing3=2)
    textbox.tag_configure("h3", font=("Segoe UI", 11, "bold"), spacing1=4)
    textbox.tag_configure("bold", font=("Segoe UI", 10, "bold"))
    textbox.tag_configure("inline_code", font=("Consolas", 9),
                           background="#F3F4F6", foreground="#D63384")
    textbox.tag_configure("code_block_bg", background="#F8F8F8",
                           lmargin1=10, lmargin2=10,
                           font=("Consolas", 9), spacing1=4, spacing3=4)

    parts = re.split(r"(```[\w+\-]*\n.*?\n```)", content, flags=re.DOTALL)
    for part in parts:
        if part.startswith("```"):
            m = re.match(r"```([\w+\-]*)\n(.*?)\n```", part, re.DOTALL)
            if m:
                lang = (m.group(1) or "").lower()
                code = m.group(2)
                textbox.insert("end", "\n")
                start = textbox.index("end")
                _insert_highlighted_code(textbox, code, lang_hint=lang)
                end = textbox.index("end")
                textbox.tag_add("code_block_bg", start, end)
                textbox.insert("end", "\n")
            else:
                textbox.insert("end", part)
            continue
        for line in part.split("\n"):
            if line.startswith("# "):
                textbox.insert("end", line[2:] + "\n", "h1")
            elif line.startswith("## "):
                textbox.insert("end", line[3:] + "\n", "h2")
            elif line.startswith("### "):
                textbox.insert("end", line[4:] + "\n", "h3")
            else:
                pieces = re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", line)
                for piece in pieces:
                    if piece.startswith("`") and piece.endswith("`") and len(piece) > 2:
                        textbox.insert("end", piece[1:-1], "inline_code")
                    elif piece.startswith("**") and piece.endswith("**") and len(piece) > 4:
                        textbox.insert("end", piece[2:-2], "bold")
                    else:
                        textbox.insert("end", piece)
                textbox.insert("end", "\n")
    textbox.configure(state="disabled")


# ─── Main window ─────────────────────────────────────────────────────────────
class HappyApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        # ASCII title — em-dash drops from WM_NAME in some frozen Tcl/Tk builds.
        self.title(f"Happy AI Agent  v{VERSION}")
        self.geometry("1280x820")
        self.minsize(900, 600)
        try:
            if ICON_PATH.exists():
                self.iconbitmap(default=str(ICON_PATH))
        except Exception:
            pass

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=HAPPY_BG)

        self.app_state = AppState()
        self.app_state.auto_auth()
        self._update_info = None  # updater.UpdateInfo when newer release found

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, self)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.pages: Dict[str, ctk.CTkFrame] = {}
        for cls in (HomeFrame, SettingsFrame, RunningFrame, DoneFrame):
            self.pages[cls.PAGE_ID] = cls(self.main, self)

        self.current_page = "home"
        self.show_page("home")

        self.after(200, self._drain_pipeline_queue)
        # Schedule a non-blocking update check 3 sec after the window appears.
        self.after(3000, self._kick_update_check)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _kick_update_check(self):
        """Background-check GitHub Releases for a newer version. Silent if no
        network / repo not configured / already on latest."""
        def worker():
            try:
                info = updater.check_for_update(VERSION, timeout=4.0)
            except Exception:
                info = None
            if info:
                self.after(0, lambda i=info: self._on_update_found(i))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_found(self, info):
        self._update_info = info
        try:
            self.sidebar.show_update_pill(info)
        except Exception:
            pass

    def offer_install_update(self):
        """User clicked the 'Update available' pill — download + relaunch."""
        info = self._update_info
        if not info:
            return
        if not messagebox.askyesno(
            f"Update {info.tag} พร้อมแล้ว",
            f"มี Happy AI Agent v{info.version} ออกแล้ว (เครื่องคุณคือ v{VERSION})\n\n"
            f"กด Yes → ดาวน์โหลด + ติดตั้งทับอัตโนมัติ\n"
            f"กด No → ข้ามไปก่อน (ปุ่มยังอยู่ที่ sidebar)",
        ):
            return

        # Progress dialog
        win = ctk.CTkToplevel(self)
        win.title("กำลังดาวน์โหลด update")
        win.geometry("480x150")
        win.transient(self)
        win.grab_set()
        if ICON_PATH.exists():
            win.after(250, lambda: win.iconbitmap(str(ICON_PATH)))
        ctk.CTkLabel(win, text=f"⬇ กำลังดาวน์โหลด Happy AI Agent {info.tag}...",
                      font=("Segoe UI", 13, "bold"),
                      text_color=HAPPY_ORANGE
                      ).pack(pady=(20, 6))
        msg = ctk.CTkLabel(win, text="กำลังเริ่ม...", font=("Segoe UI", 10))
        msg.pack(pady=2)
        prog = ctk.CTkProgressBar(win, progress_color=HAPPY_PINK)
        prog.set(0)
        prog.pack(padx=20, pady=8, fill="x")

        cancel_event = threading.Event()
        dest = updater.cache_dir() / updater.INSTALLER_ASSET_NAME

        def progress_cb(done, total):
            pct = done / max(total, 1)
            self.after(0, lambda p=pct, d=done, t=total: (
                prog.set(p),
                msg.configure(text=f"{d/1024/1024:.1f} / {t/1024/1024:.1f} MB"),
            ))

        def worker():
            ok, m = updater.download_installer(
                info.download_url, dest, progress_cb=progress_cb,
                cancel_event=cancel_event,
            )
            if ok:
                self.after(0, lambda: (
                    win.grab_release(), win.destroy(),
                    updater.launch_installer_and_exit(dest, silent=True),
                ))
            else:
                self.after(0, lambda mm=m: (
                    win.grab_release(), win.destroy(),
                    messagebox.showerror("ดาวน์โหลดไม่สำเร็จ", mm),
                ))

        threading.Thread(target=worker, daemon=True).start()

    def show_page(self, page_id: str):
        for frame in self.pages.values():
            frame.grid_forget()
        page = self.pages[page_id]
        page.grid(row=0, column=0, sticky="nsew")
        self.current_page = page_id
        if hasattr(page, "on_show"):
            page.on_show()
        self.sidebar.refresh_history()
        self.sidebar.refresh_auth_status()

    def start_pipeline(self, task: str, settings: dict):
        session_path = create_session(task, self.app_state.model, settings)
        if self.app_state.attached_files:
            save_attachments_to_session(session_path, self.app_state.attached_files)
            update_meta(session_path, has_attachments=True)

        self.app_state.current_session_path = session_path
        self.app_state.current_outputs = {}
        phases = get_phases_for_mode(settings.get("mode", "quick"))
        self.app_state.current_status = {p["id"]: "pending" for p in phases}
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

        def worker():
            def on_start(pid, name, idx):
                q.put(("start", pid, name, idx))
            def on_complete(pid, name, idx, output):
                q.put(("complete", pid, name, idx, output))
            def on_error(pid, name, err):
                q.put(("error", pid, name, err))
            def on_judge(round_num, decision, score):
                q.put(("judge", round_num, decision, score))

            runner = PipelineRunner(
                client=self.app_state.client, model=self.app_state.model,
                delay=settings["delay"],
                judge_threshold=settings["judge_threshold"],
                max_judge_loops=settings["max_judge_loops"],
                mode=settings["mode"],
                attachments=attachments,
                on_phase_start=on_start, on_phase_complete=on_complete,
                on_phase_error=on_error, on_judge_round=on_judge,
                should_stop=lambda: stop_flag.get("stop", False),
            )
            try:
                runner.run(task, session_path)
                if stop_flag.get("stop"):
                    try:
                        update_meta(session_path, status="stopped",
                                    stopped_at=datetime.now().isoformat(),
                                    stopped_by_user=True)
                    except Exception:
                        pass
                    q.put(("stopped",))
                else:
                    q.put(("done",))
            except Exception as e:
                try:
                    update_meta(session_path, status="failed",
                                failed_at=datetime.now().isoformat(),
                                last_error=str(e)[:300])
                except Exception:
                    pass
                q.put(("fatal", str(e)[:300]))

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.app_state.pipeline_thread = t
        self.show_page("running")

    def stop_pipeline(self):
        if self.app_state.pipeline_thread and self.app_state.pipeline_thread.is_alive():
            self.app_state.stop_flag["stop"] = True

    def _drain_pipeline_queue(self):
        q = self.app_state.pipeline_queue
        if q is not None:
            try:
                while True:
                    msg = q.get_nowait()
                    self._handle_pipeline_msg(msg)
            except queue.Empty:
                pass
        self.after(200, self._drain_pipeline_queue)

    def _handle_pipeline_msg(self, msg):
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
            self.app_state.current_judge_rounds.append((round_num, decision, score))
        elif kind in ("done", "stopped"):
            self.app_state.running = False
            self.app_state.pipeline_queue = None
            self.show_page("done")
            return
        elif kind == "fatal":
            self.app_state.running = False
            self.app_state.pipeline_queue = None
            messagebox.showerror("Pipeline ผิดพลาด", f"Pipeline ล้มเหลว:\n{msg[1]}")
            self.show_page("done")
            return

        if self.current_page == "running":
            self.pages["running"].refresh()

    def _on_close(self):
        self.app_state.save_settings()
        if self.app_state.running:
            self.app_state.stop_flag["stop"] = True
        self.destroy()


# ─── Sidebar ─────────────────────────────────────────────────────────────────
class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, app: "HappyApp"):
        super().__init__(parent, width=230, fg_color=HAPPY_SIDEBAR_BG,
                         border_width=0, corner_radius=0)
        self.app = app
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        # Top accent band — orange→pink visual cue
        top_band = ctk.CTkFrame(self, fg_color=HAPPY_ORANGE,
                                  corner_radius=0, height=4)
        top_band.grid(row=99, column=0, sticky="ew")  # row 99 = behind logo

        # Logo image at top — falls back to text if image missing
        self._logo_img = load_logo_image(target_width=180)
        if self._logo_img is not None:
            ctk.CTkLabel(self, image=self._logo_img, text=""
                          ).grid(row=0, column=0, pady=(18, 6), padx=20)
            ctk.CTkLabel(self, text="AI AGENT", font=("Segoe UI", 9),
                          text_color=HAPPY_MUTED
                          ).grid(row=1, column=0, pady=(0, 16), padx=20)
        else:
            ctk.CTkLabel(self, text="🤖 Happy", font=("Segoe UI", 22, "bold"),
                          text_color=HAPPY_ORANGE).grid(row=0, column=0,
                                                         pady=(20, 0), padx=20, sticky="w")
            ctk.CTkLabel(self, text="AI Agent", font=("Segoe UI", 10),
                          text_color=HAPPY_MUTED).grid(row=1, column=0,
                                                         pady=(0, 18), padx=20, sticky="w")

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=2, column=0, padx=10, sticky="ew")
        nav.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(nav, text="🏠  หน้าหลัก", anchor="w", height=36,
                       fg_color="white", text_color=HAPPY_TEXT,
                       hover_color=TINT_ORANGE,
                       border_width=1, border_color="#E5E7EB",
                       font=("Segoe UI", 11), corner_radius=10,
                       command=lambda: self.app.show_page("home")
                       ).grid(row=0, column=0, sticky="ew", pady=3)
        ctk.CTkButton(nav, text="⚙️  ตั้งค่า", anchor="w", height=36,
                       fg_color="white", text_color=HAPPY_TEXT,
                       hover_color=TINT_ORANGE,
                       border_width=1, border_color="#E5E7EB",
                       font=("Segoe UI", 11), corner_radius=10,
                       command=lambda: self.app.show_page("settings")
                       ).grid(row=1, column=0, sticky="ew", pady=3)

        ctk.CTkLabel(self, text="📜  ประวัติ", anchor="w",
                      font=("Segoe UI", 11, "bold"),
                      text_color=HAPPY_TEXT
                      ).grid(row=3, column=0,
                              padx=20, pady=(20, 4), sticky="w")

        self.history_frame = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                                       width=200)
        self.history_frame.grid(row=4, column=0, padx=8, sticky="nsew")
        self.grid_rowconfigure(4, weight=1)

        self.auth_status = ctk.CTkLabel(self, text="", font=("Segoe UI", 10, "bold"),
                                          text_color=HAPPY_MUTED, wraplength=190,
                                          justify="left", anchor="w",
                                          fg_color=TINT_YELLOW, corner_radius=8,
                                          padx=10, pady=8)
        self.auth_status.grid(row=5, column=0, padx=12, pady=(14, 4), sticky="ew")

        # Update pill — hidden by default; shown by show_update_pill() when a
        # newer release is found by HappyApp._kick_update_check.
        self.update_pill = ctk.CTkButton(
            self, text="", font=("Segoe UI", 10, "bold"),
            fg_color=GREEN, hover_color="#15803D", text_color="white",
            corner_radius=8, height=32,
            command=lambda: self.app.offer_install_update(),
        )
        # (not gridded yet — only when update is found)

        self.refresh_auth_status()
        self.refresh_history()

    def show_update_pill(self, info):
        """Called by HappyApp when updater.check_for_update returned a newer
        release. Reveals a green pill with the version → click to install."""
        try:
            self.update_pill.configure(text=f"🟢 Update {info.tag}  →")
            self.update_pill.grid(row=6, column=0, padx=12, pady=(0, 14), sticky="ew")
        except Exception:
            pass

    def refresh_auth_status(self):
        if self.app.app_state.auth_ready:
            k = self.app.app_state.api_key
            masked = f"{k[:6]}...{k[-4:]}" if len(k) > 12 else "***"
            self.auth_status.configure(text=f"🟢 เชื่อมต่อแล้ว\nkey: {masked}",
                                         text_color=GREEN)
        else:
            self.auth_status.configure(text="🔴 ยังไม่เชื่อมต่อ\nเปิด Settings",
                                         text_color=RED)

    def refresh_history(self):
        for child in self.history_frame.winfo_children():
            child.destroy()
        sessions = list_sessions()[:10]
        if not sessions:
            ctk.CTkLabel(self.history_frame, text="(ยังไม่มีงาน)",
                          text_color=HAPPY_MUTED, font=("Segoe UI", 9)
                          ).pack(pady=4, padx=4, anchor="w")
            return
        for s in sessions:
            preview = (s["task_preview"] or "(ไม่มีโจทย์)").strip()[:26]
            icon = ("✅" if s["status"] == "completed"
                    else "⏳" if s["status"] == "running"
                    else "⚠")
            row = ctk.CTkFrame(self.history_frame, fg_color="transparent")
            row.pack(fill="x", pady=1, padx=2)
            row.grid_columnconfigure(0, weight=1)

            btn = ctk.CTkButton(
                row, text=f"{icon} {preview}…", anchor="w", height=26,
                fg_color="transparent", text_color=HAPPY_TEXT,
                hover_color=HAPPY_BG, font=("Segoe UI", 9),
                command=lambda sp=s["path"], st=s["status"]: self._open(sp, st),
            )
            btn.grid(row=0, column=0, sticky="ew")
            ctk.CTkButton(
                row, text="🗑", width=24, height=26,
                fg_color="transparent", text_color=HAPPY_MUTED,
                hover_color="#FEE2E2", font=("Segoe UI", 9),
                command=lambda sp=s["path"]: self._delete(sp),
            ).grid(row=0, column=1)

    def _open(self, sp, status):
        try:
            data = load_session(sp)
            self.app.app_state.current_session_path = sp
            self.app.app_state.current_outputs = data["outputs"]
            self.app.show_page("running" if status == "running" else "done")
        except Exception as e:
            messagebox.showerror("เปิดไม่ได้", str(e))

    def _delete(self, sp):
        if not messagebox.askyesno("ลบ session?", f"ลบ '{sp.name}' หรือไม่?"):
            return
        try:
            delete_session(sp)
            if self.app.app_state.current_session_path == sp:
                self.app.app_state.current_session_path = None
                self.app.show_page("home")
            else:
                self.refresh_history()
        except Exception as e:
            messagebox.showerror("ลบไม่ได้", str(e))


# ─── Home page ───────────────────────────────────────────────────────────────
class HomeFrame(ctk.CTkFrame):
    PAGE_ID = "home"

    def __init__(self, parent, app: "HappyApp"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Simple logo header (matching Streamlit's render_header)
        self._logo_img = load_logo_image(target_width=260)
        if self._logo_img is not None:
            ctk.CTkLabel(self, image=self._logo_img, text=""
                          ).grid(row=0, column=0, pady=(4, 8), sticky="w")
        else:
            ctk.CTkLabel(self, text="🤖 Happy AI Agent",
                          font=("Segoe UI", 22, "bold"),
                          text_color=HAPPY_ORANGE, anchor="w"
                          ).grid(row=0, column=0, sticky="ew", pady=(4, 4))

        # Thin horizontal divider
        ctk.CTkFrame(self, fg_color=HAPPY_BORDER, height=2,
                       corner_radius=1
                       ).grid(row=1, column=0, sticky="ew", pady=(0, 14))

        # The auth-warning + go-to-settings button (shown via on_show)
        self.auth_warn_frame = ctk.CTkFrame(
            self, fg_color=TINT_YELLOW,
            border_color="#FBBF24", border_width=2, corner_radius=12,
        )
        self.auth_warn_frame.grid_columnconfigure(0, weight=1)
        self.auth_warn_label = ctk.CTkLabel(
            self.auth_warn_frame,
            text="⚠️  ยังไม่ได้เชื่อมต่อ Gemini — ไปที่ ⚙️ ตั้งค่า ก่อนครับ",
            font=("Segoe UI", 12, "bold"),
            text_color="#78350F", anchor="w",
        )
        self.auth_warn_label.grid(row=0, column=0, sticky="ew", padx=14, pady=12)
        self.go_settings_btn = make_gradient_button(
            self, "⚙️  ไปหน้าตั้งค่า",
            command=lambda: self.app.show_page("settings"),
            width=1400, height=46, radius=23,
            font=("Segoe UI", 13, "bold"),
        )
        # (gridded conditionally in on_show)

        # Section header
        ctk.CTkLabel(self, text="💭 อยากให้น้องช่วยทำอะไร?",
                      font=("Segoe UI", 17, "bold"),
                      text_color=HAPPY_TEXT, anchor="w"
                      ).grid(row=4, column=0, sticky="nw", pady=(2, 8))

        self.task_input = ctk.CTkTextbox(
            self, height=180, fg_color="white",
            border_color=HAPPY_BORDER, border_width=2,
            corner_radius=12,
            font=("Segoe UI", 11),
        )
        self.task_input.grid(row=5, column=0, sticky="nsew", pady=(0, 12))
        self.task_input.insert(
            "1.0",
            "ตัวอย่าง:\n"
            "สร้างเครื่องคิดเลขแบบหน้าเว็บไฟล์เดียว (HTML+CSS+JS รวมในไฟล์เดียว) "
            "มีปุ่ม 0-9, + - × ÷, =, C ดีไซน์สวย ใช้งานบนมือถือได้"
        )

        # Attach files — simple white card, only shown in thorough mode
        self.attach_frame = ctk.CTkFrame(self, fg_color="white",
                                            border_color=HAPPY_BORDER,
                                            border_width=1, corner_radius=10)
        self.attach_frame.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        self.attach_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(self.attach_frame, text="📎 แนบไฟล์อ้างอิง",
                       fg_color=TINT_ORANGE, text_color="#78350F",
                       hover_color="#FDBA74",
                       font=("Segoe UI", 11, "bold"),
                       corner_radius=10,
                       command=self._pick_files
                       ).grid(row=0, column=0, padx=10, pady=8)
        self.attach_label = ctk.CTkLabel(self.attach_frame,
                                            text="(ยังไม่มีไฟล์แนบ — ใช้เฉพาะ Thorough mode)",
                                            text_color=HAPPY_MUTED, anchor="w")
        self.attach_label.grid(row=0, column=1, padx=10, pady=8, sticky="ew")

        # Info strip — plain text muted
        self.info_label = ctk.CTkLabel(self, text="", anchor="w",
                                          font=("Segoe UI", 10),
                                          text_color=HAPPY_MUTED)
        self.info_label.grid(row=7, column=0, sticky="ew", pady=(2, 12))

        # Gradient start button (signature orange→pink CTA)
        self.start_btn = make_gradient_button(
            self, "▶️   ให้น้องช่วยทำ!",
            command=self._start,
            width=1600, height=58, radius=29,
            font=("Segoe UI", 16, "bold"),
        )
        self.start_btn.grid(row=8, column=0, sticky="ew")

    def on_show(self):
        self._update_info()
        if self.app.app_state.pipeline_mode == "thorough":
            self.attach_frame.grid()
        else:
            self.attach_frame.grid_remove()
        # Show auth warning + go-to-settings only if not authenticated
        if not self.app.app_state.auth_ready:
            self.auth_warn_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
            self.go_settings_btn.grid(row=3, column=0, sticky="ew", pady=(0, 14))
            self.start_btn.configure(state="disabled")
        else:
            self.auth_warn_frame.grid_remove()
            self.go_settings_btn.grid_remove()
            self.start_btn.configure(state="normal")

    def _update_info(self):
        s = self.app.app_state
        n = len(s.attached_files)
        mode = "🚀 Thorough" if s.pipeline_mode == "thorough" else "⚡ Quick"
        files = f"   •   📎 {n} ไฟล์" if n else ""
        self.info_label.configure(
            text=f"🤖 {s.model}   •   ⏱ {s.delay}s   •   ⚖ {s.judge_threshold}/100   •   {mode}{files}"
        )

    def _pick_files(self):
        if self.app.app_state.pipeline_mode != "thorough":
            messagebox.showinfo("เฉพาะ Thorough mode",
                                  "ไฟล์แนบใช้ได้เฉพาะ Thorough mode\n"
                                  "ไปเปลี่ยน mode ที่ ⚙️ ตั้งค่า")
            return
        paths = filedialog.askopenfilenames(
            title="แนบไฟล์อ้างอิง",
            filetypes=[
                ("รองรับ", "*.png *.jpg *.jpeg *.webp *.gif *.pdf "
                              "*.docx *.xlsx *.csv *.txt *.md"),
                ("ทุกไฟล์", "*.*"),
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
        if files:
            names = ", ".join(f[0] for f in files[:3])
            extra = f" +{len(files)-3} ไฟล์" if len(files) > 3 else ""
            kb = sum(len(b) for _, b in files) / 1024
            self.attach_label.configure(
                text=f"📎 {len(files)} ไฟล์: {names}{extra}  ({kb:.1f} KB)",
                text_color=HAPPY_TEXT,
            )
        else:
            self.attach_label.configure(text="(ไม่มีไฟล์ที่รองรับ)",
                                          text_color=HAPPY_MUTED)
        self._update_info()

    def _start(self):
        if not self.app.app_state.auth_ready:
            messagebox.showwarning("ยังไม่เชื่อมต่อ",
                                     "ไปที่ ⚙️ ตั้งค่า เพื่อใส่ Gemini API key ก่อนครับ")
            self.app.show_page("settings")
            return
        task = self.task_input.get("1.0", "end").strip()
        if not task:
            messagebox.showwarning("ยังไม่ได้พิมพ์โจทย์",
                                     "กรุณาใส่โจทย์ที่ต้องการให้น้องทำก่อนครับ")
            return
        s = self.app.app_state
        settings = {
            "delay": s.delay,
            "judge_threshold": s.judge_threshold,
            "max_judge_loops": s.max_judge_loops,
            "mode": s.pipeline_mode,
        }
        self.app.start_pipeline(task, settings)


# ─── Settings page ───────────────────────────────────────────────────────────
class SettingsFrame(ctk.CTkFrame):
    PAGE_ID = "settings"

    def __init__(self, parent, app: "HappyApp"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # Logo header (like other pages)
        self._logo_img = load_logo_image(target_width=240)
        if self._logo_img is not None:
            ctk.CTkLabel(scroll, image=self._logo_img, text=""
                          ).grid(row=0, column=0, pady=(4, 8), sticky="w")
        else:
            ctk.CTkLabel(scroll, text="🤖 Happy AI Agent",
                          font=("Segoe UI", 20, "bold"),
                          text_color=HAPPY_ORANGE, anchor="w"
                          ).grid(row=0, column=0, sticky="ew", pady=(4, 4))

        ctk.CTkFrame(scroll, fg_color=HAPPY_BORDER, height=2,
                       corner_radius=1
                       ).grid(row=99, column=0, sticky="ew", pady=(0, 10))  # gap row
        ctk.CTkLabel(scroll, text="⚙️  ตั้งค่า",
                      font=("Segoe UI", 26, "bold"),
                      text_color=HAPPY_TEXT, anchor="w"
                      ).grid(row=100, column=0, sticky="ew", pady=(8, 14))

        self._build_auth(scroll, row=101)
        self._build_model(scroll, row=102)
        self._build_pipeline(scroll, row=103)
        self._build_reset(scroll, row=104)

    def _make_card(self, parent, title, row, accent=HAPPY_PINK):
        """White card with thin orange border. Card title is colored per
        section so each section is visually distinct without garish accent
        strips (Nick's directive 2026-05-22: 'ของเก่าสะอาดกว่า')."""
        card = ctk.CTkFrame(parent, fg_color="white",
                              border_color=HAPPY_BORDER, border_width=1,
                              corner_radius=12)
        card.grid(row=row, column=0, sticky="ew", pady=8)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text=title, font=("Segoe UI", 15, "bold"),
                      anchor="w", text_color=accent
                      ).grid(row=0, column=0, sticky="ew",
                              padx=16, pady=(14, 6))
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        return content

    def _build_auth(self, parent, row):
        c = self._make_card(parent, "🔐 เชื่อมต่อ Gemini (AI Studio)", row,
                              accent=HAPPY_ORANGE)

        self.auth_status_label = ctk.CTkLabel(c, text="", anchor="w",
                                                 font=("Segoe UI", 11))
        self.auth_status_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        row_input = ctk.CTkFrame(c, fg_color="transparent")
        row_input.grid(row=1, column=0, sticky="ew", pady=2)
        row_input.grid_columnconfigure(0, weight=1)

        self.api_key_input = ctk.CTkEntry(
            row_input, placeholder_text="AIzaSy...  (paste API key ที่นี่)",
            show="•", font=("Consolas", 10),
        )
        self.api_key_input.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        save_btn = make_gradient_button(
            row_input, "💾  บันทึก & เชื่อมต่อ",
            command=self._save_api_key,
            width=300, height=32, radius=10,
            font=("Segoe UI", 11, "bold"),
        )
        save_btn.grid(row=0, column=1)

        ctk.CTkButton(c, text="🌐 ขอ API key ฟรีที่ AI Studio",
                       fg_color="transparent", text_color=HAPPY_ORANGE,
                       hover_color=HAPPY_BG, anchor="w",
                       command=lambda: webbrowser.open(
                           "https://aistudio.google.com/apikey")
                       ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        actions = ctk.CTkFrame(c, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions, text="🔄 ทดสอบเชื่อมต่อ",
                       fg_color="white", text_color=HAPPY_TEXT,
                       border_width=1, border_color=HAPPY_BORDER,
                       hover_color=HAPPY_BG,
                       command=self._test_connection
                       ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(actions, text="🚪 ล็อกเอาท์ (ลบ key)",
                       fg_color="white", text_color=HAPPY_TEXT,
                       border_width=1, border_color=HAPPY_BORDER,
                       hover_color="#FEE2E2",
                       command=self._logout
                       ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self._refresh_auth_status()

    def _build_model(self, parent, row):
        c = self._make_card(parent, "🤖 เลือก AI Model", row,
                              accent=HAPPY_PINK)
        models = self.app.app_state.available_models or [
            "gemini-3.1-flash-lite-preview", "gemini-3.1-flash-lite",
            "gemini-2.5-flash", "gemini-2.5-flash-lite",
            "gemini-3.1-pro-preview", "gemini-2.5-pro",
        ]
        if self.app.app_state.model not in models:
            models = [self.app.app_state.model] + models

        self.model_var = ctk.StringVar(value=self.app.app_state.model)
        self.model_menu = ctk.CTkOptionMenu(
            c, values=models, variable=self.model_var,
            fg_color=HAPPY_ORANGE, button_color=HAPPY_PINK,
            button_hover_color=HAPPY_ORANGE,
            command=self._on_model_change,
        )
        self.model_menu.grid(row=0, column=0, sticky="ew", pady=2)

        ctk.CTkLabel(c, anchor="w", text_color=HAPPY_MUTED,
                      font=("Segoe UI", 9),
                      text="⭐ แนะนำ: gemini-3.1-flash-lite-preview  "
                           "(ฟรี: RPD 500, output 65K tokens)"
                      ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

        r = ctk.CTkFrame(c, fg_color="transparent")
        r.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        r.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(r, text="🔄 รีเฟรชรายชื่อ model",
                       fg_color="white", text_color=HAPPY_TEXT,
                       border_width=1, border_color=HAPPY_BORDER,
                       hover_color=HAPPY_BG,
                       command=self._refresh_models
                       ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(r, text="🧪 ทดสอบ model",
                       fg_color="white", text_color=HAPPY_TEXT,
                       border_width=1, border_color=HAPPY_BORDER,
                       hover_color=HAPPY_BG,
                       command=self._test_model
                       ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _build_pipeline(self, parent, row):
        c = self._make_card(parent, "⚡ การทำงาน", row,
                              accent=HAPPY_YELLOW)

        ctk.CTkLabel(c, text="โหมด", anchor="w",
                      font=("Segoe UI", 11, "bold")
                      ).grid(row=0, column=0, sticky="w")
        self.mode_var = ctk.StringVar(value=self.app.app_state.pipeline_mode)
        mode_row = ctk.CTkFrame(c, fg_color="transparent")
        mode_row.grid(row=1, column=0, sticky="ew", pady=(2, 12))
        mode_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkRadioButton(mode_row, text="⚡ Quick (11 phases, ~10 นาที)",
                            variable=self.mode_var, value="quick",
                            fg_color=HAPPY_ORANGE,
                            command=self._on_mode_change
                            ).grid(row=0, column=0, sticky="w")
        ctk.CTkRadioButton(mode_row, text="🚀 Thorough (18 phases, ~20 นาที)",
                            variable=self.mode_var, value="thorough",
                            fg_color=HAPPY_ORANGE,
                            command=self._on_mode_change
                            ).grid(row=0, column=1, sticky="w")

        self.delay_label = ctk.CTkLabel(
            c, anchor="w",
            text=f"⏱ พักระหว่าง phase: {self.app.app_state.delay} วินาที")
        self.delay_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.delay_slider = ctk.CTkSlider(
            c, from_=30, to=180, number_of_steps=30,
            command=self._on_delay_change,
            button_color=HAPPY_RED, button_hover_color="#B91C1C",
            progress_color=HAPPY_RED,
        )
        self.delay_slider.set(self.app.app_state.delay)
        self.delay_slider.grid(row=3, column=0, sticky="ew", pady=(2, 0))
        ctk.CTkLabel(c, text="แนะนำ: 45s (กัน TPM hit)",
                      anchor="w", text_color=HAPPY_MUTED,
                      font=("Segoe UI", 9)
                      ).grid(row=4, column=0, sticky="w", pady=(2, 8))

        self.judge_label = ctk.CTkLabel(
            c, anchor="w",
            text=f"⚖ คะแนนผ่านขั้นต่ำของน้องผู้ตรวจ: {self.app.app_state.judge_threshold}/100")
        self.judge_label.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self.judge_slider = ctk.CTkSlider(
            c, from_=50, to=100, number_of_steps=10,
            command=self._on_judge_change,
            button_color=HAPPY_RED, button_hover_color="#B91C1C",
            progress_color=HAPPY_RED,
        )
        self.judge_slider.set(self.app.app_state.judge_threshold)
        self.judge_slider.grid(row=6, column=0, sticky="ew", pady=(2, 0))

        self.loops_label = ctk.CTkLabel(
            c, anchor="w",
            text=f"🔁 จำนวนรอบสูงสุดที่แก้ไขได้: {self.app.app_state.max_judge_loops}")
        self.loops_label.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        self.loops_slider = ctk.CTkSlider(
            c, from_=1, to=10, number_of_steps=9,
            command=self._on_loops_change,
            button_color=HAPPY_RED, button_hover_color="#B91C1C",
            progress_color=HAPPY_RED,
        )
        self.loops_slider.set(self.app.app_state.max_judge_loops)
        self.loops_slider.grid(row=8, column=0, sticky="ew", pady=(2, 0))

    def _build_reset(self, parent, row):
        c = self._make_card(parent, "🔄 รีเซ็ต", row,
                              accent=HAPPY_PURPLE)
        ctk.CTkButton(c, text="🧹 รีเซ็ตค่าตั้งกลับเป็นค่าเริ่มต้น",
                       fg_color="white", text_color=HAPPY_TEXT,
                       border_width=1, border_color=HAPPY_BORDER,
                       hover_color=HAPPY_BG,
                       command=self._reset_settings
                       ).grid(row=0, column=0, sticky="ew")

    def _refresh_auth_status(self):
        if self.app.app_state.auth_ready:
            k = self.app.app_state.api_key
            masked = f"{k[:6]}...{k[-4:]}" if len(k) > 12 else "***"
            self.auth_status_label.configure(
                text=f"✅ เชื่อมต่อแล้ว — key: {masked}", text_color=GREEN)
        else:
            self.auth_status_label.configure(
                text="⚠️ ยังไม่ได้เชื่อมต่อ — paste API key ที่ช่องด้านล่าง",
                text_color=RED)

    def _save_api_key(self):
        key = self.api_key_input.get().strip()
        if not key:
            messagebox.showwarning("ยังไม่มี key", "กรุณา paste API key ก่อน")
            return
        if not is_valid_key_format(key):
            messagebox.showerror(
                "Format ผิด",
                "API key ต้องขึ้นต้นด้วย 'AIza' และยาว 35 ตัวอักษรขึ้นไป")
            return
        client, err = create_client(key)
        if err:
            messagebox.showerror("สร้าง client ไม่ได้", err)
            return
        ok, msg = test_connection(client)
        if not ok:
            messagebox.showerror("เชื่อมต่อไม่ได้", msg)
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
        self.app.app_state.save_settings()
        self._refresh_auth_status()
        self.app.sidebar.refresh_auth_status()
        self.api_key_input.delete(0, "end")
        messagebox.showinfo("เชื่อมต่อแล้ว!",
                              "✅ บันทึก & เชื่อมต่อสำเร็จ!\n"
                              "ครั้งหน้าเปิด Happy AI Agent จะ auto-login ให้เลย")

    def _test_connection(self):
        if not self.app.app_state.client:
            messagebox.showwarning("ยังไม่เชื่อมต่อ", "ใส่ API key แล้วกดบันทึกก่อนครับ")
            return
        ok, msg = test_connection(self.app.app_state.client)
        if ok:
            messagebox.showinfo("ทดสอบสำเร็จ", msg)
        else:
            messagebox.showerror("ทดสอบไม่ผ่าน", msg)

    def _logout(self):
        if not messagebox.askyesno("ล็อกเอาท์?",
                                      "ลบ API key ออกจากเครื่องนี้?"):
            return
        clear_api_key()
        self.app.app_state.client = None
        self.app.app_state.api_key = ""
        self.app.app_state.auth_ready = False
        self.app.app_state.available_models = []
        self._refresh_auth_status()
        self.app.sidebar.refresh_auth_status()

    def _on_model_change(self, value):
        self.app.app_state.model = value
        self.app.app_state.save_settings()

    def _refresh_models(self):
        if not self.app.app_state.client:
            messagebox.showwarning("ยังไม่เชื่อมต่อ", "เชื่อมต่อก่อนครับ")
            return
        try:
            models = list_available_models(self.app.app_state.client) or []
            self.app.app_state.available_models = models
            self.model_menu.configure(values=models or [self.app.app_state.model])
            messagebox.showinfo("รายชื่อ model", f"พบ {len(models)} โมเดล")
        except Exception as e:
            messagebox.showerror("รีเฟรชไม่สำเร็จ", str(e)[:200])

    def _test_model(self):
        if not self.app.app_state.client:
            messagebox.showwarning("ยังไม่เชื่อมต่อ", "เชื่อมต่อก่อนครับ")
            return
        try:
            r = self.app.app_state.client.models.generate_content(
                model=self.app.app_state.model,
                contents="คุณคือ Gemini พร้อมรับงานจากผู้ใช้แล้วใช่ไหม? "
                          "ตอบเป็นภาษาไทย 1 ประโยคสั้นๆ ที่ทักทายและยืนยันว่าพร้อม",
            )
            reply = (r.text or "").strip()[:300] or "(empty)"
            messagebox.showinfo("ทดสอบ model สำเร็จ",
                                  f"✅ {self.app.app_state.model} พร้อมใช้งาน!\n\n💬 น้องตอบ: {reply}")
        except Exception as e:
            messagebox.showerror("ทดสอบ model ไม่ผ่าน", str(e)[:300])

    def _on_mode_change(self):
        self.app.app_state.pipeline_mode = self.mode_var.get()
        self.app.app_state.save_settings()

    def _on_delay_change(self, value):
        v = int(round(value))
        self.app.app_state.delay = v
        self.delay_label.configure(text=f"⏱ พักระหว่าง phase: {v} วินาที")
        self.app.app_state.save_settings()

    def _on_judge_change(self, value):
        v = int(round(value))
        self.app.app_state.judge_threshold = v
        self.judge_label.configure(text=f"⚖ คะแนนผ่านขั้นต่ำของน้องผู้ตรวจ: {v}/100")
        self.app.app_state.save_settings()

    def _on_loops_change(self, value):
        v = int(round(value))
        self.app.app_state.max_judge_loops = v
        self.loops_label.configure(text=f"🔁 จำนวนรอบสูงสุดที่แก้ไขได้: {v}")
        self.app.app_state.save_settings()

    def _reset_settings(self):
        if not messagebox.askyesno("รีเซ็ต?", "รีเซ็ตค่าตั้งกลับเป็นค่าเริ่มต้น?"):
            return
        for k, v in DEFAULTS.items():
            setattr(self.app.app_state, k, v)
        self.app.app_state.save_settings()
        self.model_var.set(self.app.app_state.model)
        self.mode_var.set(self.app.app_state.pipeline_mode)
        self.delay_slider.set(self.app.app_state.delay)
        self.judge_slider.set(self.app.app_state.judge_threshold)
        self.loops_slider.set(self.app.app_state.max_judge_loops)
        self.delay_label.configure(
            text=f"⏱ พักระหว่าง phase: {self.app.app_state.delay} วินาที")
        self.judge_label.configure(
            text=f"⚖ คะแนนผ่านขั้นต่ำของน้องผู้ตรวจ: {self.app.app_state.judge_threshold}/100")
        self.loops_label.configure(
            text=f"🔁 จำนวนรอบสูงสุดที่แก้ไขได้: {self.app.app_state.max_judge_loops}")

    def on_show(self):
        self._refresh_auth_status()


# ─── Running page ────────────────────────────────────────────────────────────
class RunningFrame(ctk.CTkFrame):
    PAGE_ID = "running"

    def __init__(self, parent, app: "HappyApp"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Logo header (consistent across pages)
        self._logo_img = load_logo_image(target_width=220)
        if self._logo_img is not None:
            ctk.CTkLabel(self, image=self._logo_img, text=""
                          ).grid(row=0, column=0, columnspan=2,
                                  pady=(4, 8), sticky="w")
        else:
            ctk.CTkLabel(self, text="🤖 Happy AI Agent",
                          font=("Segoe UI", 20, "bold"),
                          text_color=HAPPY_ORANGE, anchor="w"
                          ).grid(row=0, column=0, columnspan=2,
                                  sticky="ew", pady=(4, 4))

        # Progress card — clean white with thin border
        prog = ctk.CTkFrame(self, fg_color="white",
                              border_color=HAPPY_BORDER, border_width=1,
                              corner_radius=12)
        prog.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 10))
        prog.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(prog, text="⏳ น้องๆ กำลังทำงาน...",
                                           font=("Segoe UI", 16, "bold"),
                                           text_color=HAPPY_ORANGE_DEEP,
                                           anchor="w")
        self.title_label.grid(row=0, column=0, sticky="ew", padx=16,
                                pady=(14, 4))
        self.progress_label = ctk.CTkLabel(prog, text="",
                                              font=("Segoe UI", 11),
                                              text_color=HAPPY_MUTED,
                                              anchor="w")
        self.progress_label.grid(row=1, column=0, sticky="ew", padx=16,
                                   pady=(0, 4))
        self.progress = ctk.CTkProgressBar(prog, progress_color=HAPPY_ORANGE,
                                              fg_color="#FFEDD5", height=12,
                                              corner_radius=6)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))
        actions = ctk.CTkFrame(prog, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=16, pady=(2, 14))
        self.stop_btn = ctk.CTkButton(
            actions, text="🛑 หยุด pipeline",
            fg_color="white", text_color=HAPPY_RED,
            border_width=2, border_color=HAPPY_RED,
            hover_color="#FEE2E2",
            font=("Segoe UI", 11, "bold"), corner_radius=10,
            command=self._stop,
        )
        self.stop_btn.pack(side="left")

        self.agents_frame = ctk.CTkScrollableFrame(
            self, fg_color="white", border_color=HAPPY_BORDER,
            border_width=1, width=260, corner_radius=12,
        )
        self.agents_frame.grid(row=3, column=0, sticky="nsew",
                                 pady=(0, 12), padx=(0, 8))

        out = ctk.CTkFrame(self, fg_color="white",
                             border_color=HAPPY_BORDER, border_width=1,
                             corner_radius=12)
        out.grid(row=3, column=1, sticky="nsew", pady=(0, 12))
        out.grid_columnconfigure(0, weight=1)
        out.grid_rowconfigure(1, weight=1)
        self.output_title = ctk.CTkLabel(
            out, text="📺 Output (กดที่ชื่อ agent ด้านซ้าย)",
            font=("Segoe UI", 12, "bold"),
            text_color=HAPPY_PINK, anchor="w",
        )
        self.output_title.grid(row=0, column=0, sticky="ew",
                                 padx=14, pady=(10, 4))
        wrap = ctk.CTkFrame(out, fg_color="transparent")
        wrap.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        self.output_text = tk.Text(
            wrap, wrap="word", font=("Segoe UI", 10),
            bg="white", fg=HAPPY_TEXT, relief="flat",
            borderwidth=0, padx=10, pady=8, state="disabled",
        )
        self.output_text.grid(row=0, column=0, sticky="nsew")
        sb = ctk.CTkScrollbar(wrap, command=self.output_text.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.output_text.configure(yscrollcommand=sb.set)

        self._agent_buttons = {}
        self._tick_id = None

    def on_show(self):
        self._build_agent_list()
        self.refresh()
        self._tick()

    def _tick(self):
        if self.app.current_page != "running":
            self._tick_id = None
            return
        if self.app.app_state.started_at:
            elapsed = int(time.time() - self.app.app_state.started_at)
            self.title_label.configure(
                text=f"⏳ น้องๆ กำลังทำงาน...   {elapsed//60:02d}:{elapsed%60:02d} ผ่านไป")
        self._tick_id = self.after(1000, self._tick)

    def _build_agent_list(self):
        for child in self.agents_frame.winfo_children():
            child.destroy()
        self._agent_buttons.clear()
        mode = "quick"
        sp = self.app.app_state.current_session_path
        if sp:
            try:
                meta = json.loads((sp / "_meta.json").read_text(encoding="utf-8"))
                mode = meta.get("mode", "quick")
            except Exception:
                pass
        ctk.CTkLabel(self.agents_frame, text="📋 ทีมงาน (กดเพื่อดู output)",
                      font=("Segoe UI", 11, "bold"), anchor="w"
                      ).pack(fill="x", padx=4, pady=(4, 8))
        for ph in get_phases_for_mode(mode):
            btn = ctk.CTkButton(
                self.agents_frame,
                text=self._agent_label(ph, "pending"),
                anchor="w", height=28,
                fg_color="transparent", text_color=HAPPY_TEXT,
                hover_color=HAPPY_BG, font=("Segoe UI", 10),
                command=lambda pid=ph["id"]: self._select_agent(pid),
            )
            btn.pack(fill="x", pady=1)
            self._agent_buttons[ph["id"]] = (btn, ph)

    def _agent_label(self, ph, status, extra=""):
        icon = {"done": "✅", "running": "🔄",
                "error": "❌", "pending": "⏸"}.get(status, "⏸")
        return f"{icon} {ph['emoji']} {ph['name']}{extra}"

    def _select_agent(self, pid):
        self.app.app_state.selected_agent = pid
        self._refresh_output()

    def refresh(self):
        s = self.app.app_state
        total = len(s.current_status)
        done = sum(1 for v in s.current_status.values() if v == "done")
        if total > 0:
            self.progress.set(done / total)
            self.progress_label.configure(text=f"📊 ทำเสร็จ {done} / {total} phase")
        for pid, (btn, ph) in self._agent_buttons.items():
            status = s.current_status.get(pid, "pending")
            extra = ""
            if pid == "judge" and s.current_judge_rounds:
                last = s.current_judge_rounds[-1]
                extra = f"  ({last[1]} {last[2]}/100)"
            btn.configure(text=self._agent_label(ph, status, extra))
        if (not s.selected_agent) or s.selected_agent not in s.current_outputs:
            done_ids = [pid for pid in self._agent_buttons
                        if s.current_status.get(pid) == "done"
                        and pid in s.current_outputs]
            if done_ids:
                s.selected_agent = done_ids[-1]
        self._refresh_output()

    def _refresh_output(self):
        s = self.app.app_state
        sel = s.selected_agent
        if sel and sel in s.current_outputs:
            ph = self._agent_buttons.get(sel, (None, None))[1]
            title = f"{ph['emoji']} {ph['name']}" if ph else sel
            self.output_title.configure(text=f"📺 {title}")
            render_output_to_textbox(self.output_text, s.current_outputs[sel])
        else:
            self.output_title.configure(text="📺 รอ agent ตัวแรกทำเสร็จ...")
            self.output_text.configure(state="normal")
            self.output_text.delete("1.0", "end")
            self.output_text.insert("end", "รอ agent ตัวแรกทำเสร็จก่อน — เสร็จเมื่อไหร่ output จะแสดงที่นี่อัตโนมัติ")
            self.output_text.configure(state="disabled")

    def _stop(self):
        if not messagebox.askyesno(
                "หยุด?", "หยุด pipeline?\n(output ที่ทำแล้วจะถูกเก็บไว้)"):
            return
        self.app.stop_pipeline()
        self.stop_btn.configure(state="disabled", text="🛑 กำลังหยุด...")


# ─── Done page ───────────────────────────────────────────────────────────────
class DoneFrame(ctk.CTkFrame):
    PAGE_ID = "done"

    def __init__(self, parent, app: "HappyApp"):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Logo header
        self._logo_img = load_logo_image(target_width=220)
        if self._logo_img is not None:
            ctk.CTkLabel(self, image=self._logo_img, text=""
                          ).grid(row=0, column=0, columnspan=2,
                                  pady=(4, 4), sticky="w")
        else:
            ctk.CTkLabel(self, text="🤖 Happy AI Agent",
                          font=("Segoe UI", 20, "bold"),
                          text_color=HAPPY_ORANGE, anchor="w"
                          ).grid(row=0, column=0, columnspan=2,
                                  sticky="ew", pady=(4, 4))

        # Status header — colored text only, no big banner
        self.title_label = ctk.CTkLabel(self, text="✅ เสร็จเรียบร้อย!",
                                           font=("Segoe UI", 20, "bold"),
                                           text_color=GREEN, anchor="w")
        self.title_label.grid(row=1, column=0, columnspan=2,
                                sticky="ew", pady=(10, 2))

        self.status_label = ctk.CTkLabel(self, text="",
                                            font=("Segoe UI", 11), anchor="w",
                                            wraplength=900, justify="left",
                                            text_color=HAPPY_MUTED)
        self.status_label.grid(row=2, column=0, columnspan=2,
                                 sticky="ew", pady=(0, 12))

        # Action strip — clean white buttons + one gradient CTA for Build .exe
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        for i in range(4):
            actions.grid_columnconfigure(i, weight=1)

        self.dl_txt_btn = ctk.CTkButton(
            actions, text="📄 ดาวน์โหลดรายงาน",
            fg_color="white", text_color=HAPPY_TEXT,
            border_width=2, border_color=HAPPY_BORDER,
            hover_color=TINT_ORANGE,
            font=("Segoe UI", 11, "bold"), corner_radius=12, height=44,
            command=self._download_txt,
        )
        self.dl_txt_btn.grid(row=0, column=0, sticky="ew", padx=4)
        self.dl_code_btn = ctk.CTkButton(
            actions, text="💾 ดาวน์โหลดโค้ด",
            fg_color="white", text_color=HAPPY_TEXT,
            border_width=2, border_color=HAPPY_BORDER,
            hover_color=TINT_ORANGE,
            font=("Segoe UI", 11, "bold"), corner_radius=12, height=44,
            command=self._download_code,
        )
        self.dl_code_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.dl_all_btn = ctk.CTkButton(
            actions, text="📦 ดาวน์โหลดทั้งหมด",
            fg_color="white", text_color=HAPPY_TEXT,
            border_width=2, border_color=HAPPY_BORDER,
            hover_color=TINT_ORANGE,
            font=("Segoe UI", 11, "bold"), corner_radius=12, height=44,
            command=self._download_all,
        )
        self.dl_all_btn.grid(row=0, column=2, sticky="ew", padx=4)
        self.build_exe_btn = make_gradient_button(
            actions, "🔨   Build เป็น .exe",
            command=self._build_exe,
            width=600, height=44, radius=12,
            font=("Segoe UI", 12, "bold"),
        )
        self.build_exe_btn.grid(row=0, column=3, sticky="ew", padx=4)

        self.agents_frame = ctk.CTkScrollableFrame(
            self, fg_color="white", border_color=HAPPY_BORDER,
            border_width=1, width=260, corner_radius=12,
        )
        self.agents_frame.grid(row=4, column=0, sticky="nsew",
                                 pady=(0, 10), padx=(0, 8))

        out = ctk.CTkFrame(self, fg_color="white",
                             border_color=HAPPY_BORDER, border_width=1,
                             corner_radius=12)
        out.grid(row=4, column=1, sticky="nsew", pady=(0, 10))
        out.grid_columnconfigure(0, weight=1)
        out.grid_rowconfigure(1, weight=1)

        self.output_title = ctk.CTkLabel(
            out, text="📺 Output (กดที่ชื่อ agent ด้านซ้าย)",
            font=("Segoe UI", 12, "bold"),
            text_color=HAPPY_PINK, anchor="w",
        )
        self.output_title.grid(row=0, column=0, sticky="ew",
                                 padx=14, pady=(10, 4))
        wrap = ctk.CTkFrame(out, fg_color="transparent")
        wrap.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        self.output_text = tk.Text(
            wrap, wrap="word", font=("Segoe UI", 10),
            bg="white", fg=HAPPY_TEXT, relief="flat",
            borderwidth=0, padx=10, pady=8, state="disabled",
        )
        self.output_text.grid(row=0, column=0, sticky="nsew")
        sb = ctk.CTkScrollbar(wrap, command=self.output_text.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.output_text.configure(yscrollcommand=sb.set)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        bottom.grid_columnconfigure((0, 1), weight=1)
        self.new_task_btn = make_gradient_button(
            bottom, "🆕  สร้างงานใหม่",
            command=self._new_task,
            width=800, height=44, radius=12,
            font=("Segoe UI", 12, "bold"),
        )
        self.new_task_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            bottom, text="🗑 ลบ session นี้",
            fg_color="white", text_color=HAPPY_RED,
            border_width=2, border_color="#FCA5A5",
            hover_color="#FEE2E2", height=44,
            font=("Segoe UI", 12, "bold"), corner_radius=12,
            command=self._delete_session,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self._agent_buttons = {}
        self._meta = {}

    def on_show(self):
        sp = self.app.app_state.current_session_path
        if not sp:
            self.title_label.configure(text="(ไม่มี session)")
            return
        try:
            data = load_session(sp)
            self.app.app_state.current_outputs = data["outputs"]
            self._meta = data["meta"]
        except Exception as e:
            messagebox.showerror("โหลด session ไม่ได้", str(e))
            return
        status = self._meta.get("status", "unknown")
        if status == "completed":
            self.title_label.configure(
                text="✅ เสร็จเรียบร้อย — น้องทำครบทุก phase แล้ว!",
                text_color=GREEN)
            self.status_label.configure(
                text=f"Session: {sp.name}", text_color=HAPPY_MUTED)
        elif status == "stopped":
            self.title_label.configure(
                text="🛑 หยุดโดย user — output บางส่วนถูกเก็บไว้แล้ว",
                text_color="#D97706")
            self.status_label.configure(
                text=f"Session: {sp.name}", text_color=HAPPY_MUTED)
        elif status == "failed":
            self.title_label.configure(text="❌ Pipeline ล้มเหลว",
                                          text_color=RED)
            self.status_label.configure(
                text=f"Error: {self._meta.get('last_error', '')[:300]}",
                text_color=RED)
        else:
            self.title_label.configure(text=f"ℹ สถานะ: {status}",
                                          text_color=HAPPY_PURPLE)
            self.status_label.configure(
                text=f"Session: {sp.name}", text_color=HAPPY_MUTED)

        enabled = status == "completed"
        for btn in (self.dl_txt_btn, self.dl_code_btn,
                     self.dl_all_btn, self.build_exe_btn):
            btn.configure(state="normal" if enabled else "disabled")

        self._build_agent_list()
        outputs = self.app.app_state.current_outputs
        if outputs and ((not self.app.app_state.selected_agent)
                          or self.app.app_state.selected_agent not in outputs):
            mode = self._meta.get("mode", "quick")
            phases = get_phases_for_mode(mode)
            done_ids = [p["id"] for p in phases if p["id"] in outputs]
            if done_ids:
                self.app.app_state.selected_agent = done_ids[-1]
        self._refresh_output()

    def _build_agent_list(self):
        for child in self.agents_frame.winfo_children():
            child.destroy()
        self._agent_buttons.clear()
        ctk.CTkLabel(self.agents_frame, text="📋 ทีมงาน",
                      font=("Segoe UI", 11, "bold"), anchor="w"
                      ).pack(fill="x", padx=4, pady=(4, 8))
        mode = self._meta.get("mode", "quick")
        outputs = self.app.app_state.current_outputs
        for ph in get_phases_for_mode(mode):
            if ph["id"] not in outputs:
                continue
            btn = ctk.CTkButton(
                self.agents_frame,
                text=f"✅ {ph['emoji']} {ph['name']}",
                anchor="w", height=28,
                fg_color="transparent", text_color=HAPPY_TEXT,
                hover_color=HAPPY_BG, font=("Segoe UI", 10),
                command=lambda pid=ph["id"]: self._select(pid),
            )
            btn.pack(fill="x", pady=1)
            self._agent_buttons[ph["id"]] = (btn, ph)
        for k in sorted(outputs.keys()):
            if k.startswith("debugger_revision"):
                btn = ctk.CTkButton(
                    self.agents_frame, text=f"🔄 {k}",
                    anchor="w", height=28,
                    fg_color="transparent", text_color=HAPPY_TEXT,
                    hover_color=HAPPY_BG, font=("Segoe UI", 10),
                    command=lambda kk=k: self._select(kk),
                )
                btn.pack(fill="x", pady=1)
                self._agent_buttons[k] = (btn, {"emoji": "🔄", "name": k})

    def _select(self, pid):
        self.app.app_state.selected_agent = pid
        self._refresh_output()

    def _refresh_output(self):
        s = self.app.app_state
        sel = s.selected_agent
        if sel and sel in s.current_outputs:
            ph = self._agent_buttons.get(sel, (None, None))[1]
            title = f"{ph['emoji']} {ph['name']}" if ph else sel
            self.output_title.configure(text=f"📺 {title}")
            render_output_to_textbox(self.output_text, s.current_outputs[sel])
        else:
            self.output_title.configure(text="📺 (กดชื่อ agent ทางซ้ายเพื่อดู output)")
            self.output_text.configure(state="normal")
            self.output_text.delete("1.0", "end")
            self.output_text.configure(state="disabled")

    def _download_txt(self):
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
            Path(path).write_text(build_combined_txt(sp), encoding="utf-8")
            messagebox.showinfo("บันทึกแล้ว", f"บันทึกไปที่:\n{path}")
        except Exception as e:
            messagebox.showerror("บันทึกไม่ได้", str(e))

    def _download_code(self):
        sp = self.app.app_state.current_session_path
        if not sp:
            return
        try:
            files = extract_from_session(sp)
        except Exception as e:
            messagebox.showerror("แยกโค้ดไม่ได้", str(e))
            return
        if not files:
            messagebox.showwarning("ไม่มีโค้ด", "ไม่เจอ code block ใน session")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialfile=f"happy_code_{sp.name}.zip",
            filetypes=[("ZIP", "*.zip")],
        )
        if not path:
            return
        try:
            Path(path).write_bytes(build_zip(files))
            messagebox.showinfo("บันทึกแล้ว", f"บันทึกไปที่:\n{path}")
        except Exception as e:
            messagebox.showerror("บันทึกไม่ได้", str(e))

    def _download_all(self):
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
            Path(path).write_bytes(build_full_export_zip(sp, combined))
            messagebox.showinfo("บันทึกแล้ว", f"บันทึกไปที่:\n{path}")
        except Exception as e:
            messagebox.showerror("บันทึกไม่ได้", str(e))

    def _build_exe(self):
        sp = self.app.app_state.current_session_path
        if not sp:
            return
        cached = self.app.app_state.exe_built_cache.get(sp.name)
        if cached and cached.get("ok"):
            self._save_exe_from_cache(cached)
            return

        win = ctk.CTkToplevel(self)
        win.title("กำลัง Build .exe")
        win.geometry("520x180")
        win.transient(self.winfo_toplevel())
        win.grab_set()
        # Fix v2.0.4: CTkToplevel shows the default Tk feather icon by default.
        # iconbitmap must run after the window is mapped, hence after().
        if ICON_PATH.exists():
            win.after(250, lambda: win.iconbitmap(str(ICON_PATH)))
        ctk.CTkLabel(win, text="🔨 กำลัง Build .exe...",
                      font=("Segoe UI", 14, "bold"),
                      text_color=HAPPY_ORANGE
                      ).pack(pady=(20, 8))
        msg_label = ctk.CTkLabel(win, text="กำลังเตรียม...", wraplength=480,
                                    font=("Segoe UI", 10))
        msg_label.pack(pady=4, padx=20)
        prog = ctk.CTkProgressBar(win, mode="indeterminate",
                                    progress_color=HAPPY_ORANGE)
        prog.pack(pady=8, padx=20, fill="x")
        prog.start()

        result_box = {}

        def progress_cb(text):
            try:
                self.after(0, lambda t=text: msg_label.configure(text=t))
            except Exception:
                pass

        def worker():
            try:
                ok, msg, b, fname = build_exe_from_session(sp, progress_cb=progress_cb)
                result_box.update(ok=ok, message=msg, bytes=b, filename=fname)
            except Exception as e:
                result_box.update(ok=False, message=f"Build error: {e}",
                                    bytes=None, filename=None)
            self.after(0, _finish)

        def _finish():
            try:
                prog.stop()
            except Exception:
                pass
            try:
                win.grab_release()
                win.destroy()
            except Exception:
                pass
            self.app.app_state.exe_built_cache[sp.name] = result_box
            if result_box.get("ok"):
                self._save_exe_from_cache(result_box)
            else:
                messagebox.showerror("Build ไม่สำเร็จ",
                                       result_box.get("message", "unknown"))

        threading.Thread(target=worker, daemon=True).start()

    def _save_exe_from_cache(self, cached):
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
            Path(path).write_bytes(cached["bytes"])
            messagebox.showinfo("Build สำเร็จ!",
                                  f"✅ {cached.get('message', '')}\n\nบันทึกไปที่:\n{path}")
        except Exception as e:
            messagebox.showerror("บันทึกไม่ได้", str(e))

    def _new_task(self):
        self.app.app_state.current_session_path = None
        self.app.app_state.current_outputs = {}
        self.app.app_state.current_status = {}
        self.app.app_state.current_judge_rounds = []
        self.app.app_state.selected_agent = None
        self.app.show_page("home")

    def _delete_session(self):
        sp = self.app.app_state.current_session_path
        if not sp:
            return
        if not messagebox.askyesno("ลบ?", f"ลบ '{sp.name}' หรือไม่?"):
            return
        try:
            delete_session(sp)
            self.app.app_state.current_session_path = None
            self.app.app_state.current_outputs = {}
            self.app.show_page("home")
        except Exception as e:
            messagebox.showerror("ลบไม่ได้", str(e))


# ─── main ────────────────────────────────────────────────────────────────────
def _setup_crash_log():
    """In frozen --windowed builds stderr is swallowed by the bootloader, so
    any startup exception turns into a generic PyInstaller dialog with no info.
    Tee stderr to ~/.happy/crash.log so we can diagnose."""
    import sys, os
    if not getattr(sys, "frozen", False):
        return
    try:
        log_dir = Path.home() / ".happy"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "crash.log"
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        log_file.write(f"\n=== Happy AI Agent {VERSION} started at {datetime.now().isoformat()} ===\n")
        sys.stdout = log_file
        sys.stderr = log_file
    except Exception:
        pass


def main():
    _setup_crash_log()
    try:
        app = HappyApp()
        app.mainloop()
    except Exception:
        import traceback
        try:
            log_dir = Path.home() / ".happy"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "crash.log").open("a", encoding="utf-8").write(
                f"\n!!! CRASH at {datetime.now().isoformat()}\n{traceback.format_exc()}\n"
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
