"""
Happy AI Agent — Custom Setup (Creative Single-Page Hero)

Adapted from Happy Photo Organizer's pattern:
  • One screen, no wizard navigation
  • Animated gradient background (navy with orange/pink pulse)
  • Sparkles fade in/out
  • Hero card with shadow
  • Smooth phase transitions: Setup → Installing → Done

Silent mode (--silent --upgrade) used by the in-app auto-updater.

IMPORTANT: must be built with --onedir (folder mode), NOT --onefile.
PyInstaller onefile + --windowed has a known Tk window-creation bug on Windows
where the Tk window never gets a Win32 HWND. Folder mode works reliably.
The build_installer.py wraps the folder into HappyAIAgent-Setup.zip for distribution.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import tkinter as tk
from math import sin  # v2.8.0 (Cos audit B-23): hoisted from _render hot path
from PIL import Image, ImageDraw, ImageFilter, ImageTk


def enable_paste(widget):
    """Ctrl+V / right-click → Paste, robust on Thai keyboard via keycode."""
    KEYCODE_V = 86
    KEYCODE_C = 67
    KEYCODE_X = 88
    KEYCODE_A = 65
    target = getattr(widget, "_entry", widget)

    def do_paste(_e=None):
        try:
            text = target.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            target.delete("sel.first", "sel.last")
        except Exception:
            pass
        try:
            target.insert("insert", text)
        except Exception:
            pass
        return "break"

    def do_copy(_e=None):
        try:
            sel = target.selection_get()
            target.clipboard_clear()
            target.clipboard_append(sel)
        except Exception:
            pass
        return "break"

    def do_cut(_e=None):
        try:
            sel = target.selection_get()
            target.clipboard_clear()
            target.clipboard_append(sel)
            target.delete("sel.first", "sel.last")
        except Exception:
            pass
        return "break"

    def do_select_all(_e=None):
        try:
            target.select_range(0, "end")
            target.icursor("end")
        except Exception:
            pass
        return "break"

    def on_ctrl(e):
        kc = e.keycode
        if kc == KEYCODE_V:
            return do_paste()
        if kc == KEYCODE_C:
            return do_copy()
        if kc == KEYCODE_X:
            return do_cut()
        if kc == KEYCODE_A:
            return do_select_all()

    def show_menu(e):
        m = tk.Menu(target, tearoff=0)
        m.add_command(label="Cut", command=do_cut)
        m.add_command(label="Copy", command=do_copy)
        m.add_command(label="Paste", command=do_paste)
        m.add_separator()
        m.add_command(label="Select All", command=do_select_all)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    target.bind("<Control-Key>", on_ctrl)
    target.bind("<Button-3>", show_menu)


# ─── Theme — dark cosmic (navy + orange/pink) ─────────────────
COLOR_BG = "#0F172A"
COLOR_CARD = "#1E293B"
COLOR_CARD_LIGHT = "#334155"
COLOR_PRIMARY = "#FB923C"   # orange
COLOR_ACCENT = "#EC4899"    # pink
COLOR_TEXT = "#F1F5F9"
COLOR_MUTED = "#94A3B8"
COLOR_OK = "#10B981"
COLOR_WARN = "#F59E0B"
COLOR_DANGER = "#EF4444"

APP_NAME = "HappyAIAgent"           # file-system name (folder, exe, shortcut, reg key)
APP_DISPLAY_NAME = "Happy AI Agent"  # user-facing display name
APP_EXE_NAME = "HappyAIAgent.exe"
REG_KEY_NAME = "HappyAIAgent"        # HKCU uninstall key


def _read_version() -> str:
    """Read VERSION from disk (frozen bundle or source mode)."""
    mp = getattr(sys, "_MEIPASS", None)
    candidates = []
    if mp:
        candidates.append(Path(mp) / "VERSION")
    candidates.append(Path(__file__).resolve().parent.parent / "VERSION")
    for p in candidates:
        try:
            if p.exists():
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v
        except Exception:
            pass
    return "0.0.0"


APP_VERSION = _read_version()
DEFAULT_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "HappyAIAgent"

LICENSE_TEXT = f"""Happy AI Agent
Personal Use License Agreement
Version {APP_VERSION}
================================================================

ขอบคุณที่เลือกใช้ Happy AI Agent

1. License Grant (สัญญาอนุญาต)
   • ใช้ได้ฟรีสำหรับ personal use และเรียนรู้
   • Resell หรือ commercial redistribution ต้องขออนุญาต
     เป็นลายลักษณ์อักษรจากผู้พัฒนา (Nick Suksantr)

2. User Responsibilities
   • คุณต้องเตรียม Gemini API key เอง (ฟรีหรือ paid ก็ได้)
   • AI API costs ทั้งหมดเป็นความรับผิดชอบของคุณ
   • App นี้ไม่เก็บข้อมูลคุณ ยกเว้นที่จำเป็นต่อการทำงาน
     (requests ไปยัง Gemini API)

3. Warranty
   • Provided "as-is", ไม่มี warranty
   • ผู้พัฒนาไม่รับผิดชอบความเสียหายที่อาจเกิดขึ้น
   • ลองใช้ใน non-critical environment ก่อน

4. Updates
   • Auto-update via GitHub Releases (เช็คทุกครั้งที่เปิดแอป)
   • Update เป็น optional — ไม่บังคับ

5. Termination
   • ถอนการติดตั้งได้ทุกเมื่อจาก Settings > Apps & features
     (หรือรัน uninstall.bat ในโฟลเดอร์ติดตั้ง)
   • API key จะอยู่ที่ ~/.happy/auth.json — ลบมือเองถ้าต้องการ

================================================================
💡 Tips ระหว่างรอติดตั้ง

  •  พิมพ์โจทย์ภาษาไทยหรือ English ก็ได้ — น้องๆ AI เข้าใจทั้งคู่
  •  Quick mode (11 phases ~10 นาที) เหมาะกับงานทั่วไป
  •  Thorough mode (18 phases ~20 นาที) แนบไฟล์อ้างอิงได้
     — ภาพ, PDF, Excel, Word, CSV
  •  ผลลัพธ์ที่ได้คือโค้ดที่รันได้จริง — Python หรือ HTML/JS
  •  กดปุ่ม "🔨 Build เป็น .exe" ตอนเสร็จ → ได้ .exe ทันที
  •  Judge agent ตรวจคุณภาพ 0-100/100 — auto-revise ถ้าไม่ผ่าน
  •  Sessions เก็บที่ ~/.happy/sessions/ เรียกกลับมาดูได้

= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
สร้างด้วย ♥  โดย Nick & Codey (Happy AI Family)
"""


def get_payload_path():
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "payload" / "HappyAIAgent.zip"
    return Path(__file__).resolve().parent.parent / "dist" / "HappyAIAgent.zip"


def get_asset(name: str):
    if hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / "assets" / name
    else:
        p = Path(__file__).resolve().parent.parent / "assets" / name
    return p if p.exists() else None


# ─── Animated gradient background ─────────────────────────────

class GradientBackground(ctk.CTkCanvas):
    """Canvas painting animated gradient + sparkles"""

    def __init__(self, master, **kw):
        super().__init__(master, highlightthickness=0, bd=0, **kw)
        self.configure(bg=COLOR_BG)
        self._phase = 0.0
        self._sparkles = []
        self._after_id = None
        self.bind("<Configure>", self._on_resize)
        self._gradient_img_id = None
        self._last_size = (0, 0)
        self._cached_gradient = None
        self._photo = None

    def _on_resize(self, _ev):
        self._render()

    def start(self):
        self._tick()

    def stop(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self):
        self._phase = (self._phase + 0.005) % 1.0
        if random.random() < 0.04 and self.winfo_width() > 100:
            self._sparkles.append({
                "x": random.randint(20, max(21, self.winfo_width() - 20)),
                "y": random.randint(20, max(21, self.winfo_height() - 20)),
                "r": random.uniform(1.5, 3.5),
                "life": 0.0,
                "max_life": random.uniform(1.5, 3.0),
            })
        new_sparkles = []
        for s in self._sparkles:
            s["life"] += 0.05
            if s["life"] < s["max_life"]:
                new_sparkles.append(s)
        self._sparkles = new_sparkles
        self._render()
        self._after_id = self.after(50, self._tick)

    def _render(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4 or h < 4:
            return
        if (self._cached_gradient is None) or self._last_size != (w, h):
            self._last_size = (w, h)
            img = Image.new("RGB", (w, h))
            draw = ImageDraw.Draw(img)
            for y in range(h):
                t = y / max(h - 1, 1)
                # navy → slightly warmer dusty purple
                r = int(0x0F * (1 - t) + 0x28 * t)
                g = int(0x17 * (1 - t) + 0x18 * t)
                b = int(0x2A * (1 - t) + 0x38 * t)
                draw.line([(0, y), (w, y)], fill=(r, g, b))
            self._cached_gradient = img
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        # v2.8.0 (B-23): `sin` imported at module top now.
        pulse = (sin(self._phase * 6.283) + 1) / 2
        glow_alpha = int(20 + 18 * pulse)
        glow_r = min(w, h) // 3
        cx, cy = w // 2, h // 4
        odraw.ellipse(
            (cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r),
            fill=(0xFB, 0x92, 0x3C, glow_alpha),
        )
        odraw.ellipse(
            (cx - glow_r // 2, cy + glow_r, cx + glow_r // 2, cy + 2 * glow_r),
            fill=(0xEC, 0x48, 0x99, glow_alpha // 2),
        )
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=min(w, h) // 12))
        composed = Image.alpha_composite(self._cached_gradient.convert("RGBA"), overlay)
        sd = ImageDraw.Draw(composed)
        for s in self._sparkles:
            life_ratio = s["life"] / s["max_life"]
            if life_ratio < 0.4:
                alpha = int(life_ratio / 0.4 * 220)
            else:
                alpha = int((1 - (life_ratio - 0.4) / 0.6) * 220)
            sd.ellipse(
                (s["x"] - s["r"], s["y"] - s["r"], s["x"] + s["r"], s["y"] + s["r"]),
                fill=(255, 240, 200, max(0, min(255, alpha))),
            )
        # v2.8.0 (B-23): ImageTk imported at module top now.
        self._photo = ImageTk.PhotoImage(composed)
        if self._gradient_img_id is None:
            self._gradient_img_id = self.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.itemconfig(self._gradient_img_id, image=self._photo)


# ─── Installer logic ─────────────────────────────────────────

class Installer:
    """Performs actual install: extract, save key, shortcuts, registry, uninstall.bat"""

    def __init__(self):
        self.install_dir = None
        self.api_key = ""
        self.create_desktop_shortcut = True
        self.create_start_menu = True
        self.launch_after = True

    def install(self, progress_cb=None):
        try:
            assert self.install_dir is not None
            if progress_cb:
                progress_cb(0, "เริ่มติดตั้ง...")
                time.sleep(0.15)
                progress_cb(3, "เตรียมโฟลเดอร์ติดตั้ง...")
            self.install_dir.mkdir(parents=True, exist_ok=True)

            # v2.7.2 (Nick caught live tkinter ModuleNotFoundError after
            # upgrade): zip extract MERGES files on top of whatever is
            # already there, so when v2.7.0/v2.7.1 had
            # `_internal/python-embed/python313._pth` (Windows embeddable
            # layout) and v2.7.2 ships a python-build-standalone tree
            # WITHOUT that `._pth`, the stale file survives. Result: the
            # new python.exe runs in the OLD `._pth`-restricted sys.path
            # → can't find `DLLs/_tkinter.pyd` → ModuleNotFoundError.
            #
            # Fix: wipe `_internal/python-embed/` before extract. The user
            # auth.json + sessions live in `~/.happy/` so this is safe.
            # We don't wipe the whole install_dir because the desktop
            # shortcut may be in use and re-creating it on every install
            # triggers an "icon cache miss" flash.
            stale_embed = self.install_dir / "_internal" / "python-embed"
            if stale_embed.exists():
                if progress_cb:
                    progress_cb(5, "ลบ Python toolchain เดิม...")
                shutil.rmtree(stale_embed, ignore_errors=True)

            payload = get_payload_path()
            if not payload or not payload.exists():
                return False, f"Payload not found: {payload}"

            if progress_cb:
                progress_cb(8, "อ่าน payload...")
                time.sleep(0.1)
                progress_cb(12, "แตกไฟล์...")
            with zipfile.ZipFile(payload, "r") as zf:
                members = zf.namelist()
                total = len(members)
                for i, member in enumerate(members):
                    zf.extract(member, str(self.install_dir))
                    if progress_cb:
                        pct = 12 + int(74 * (i + 1) / total)
                        progress_cb(pct, f"แตก {Path(member).name[:40]}")

            if progress_cb:
                progress_cb(86, "บันทึก API key...")
            if self.api_key:
                # v2.8.0 (Cos audit B-24): atomic write so an installer
                # crash mid-save doesn't truncate auth.json and silently
                # lose the user's API key. tempfile + os.replace pattern
                # — same as core/persistence._atomic_write_text.
                cfg_dir = Path.home() / ".happy"
                cfg_dir.mkdir(parents=True, exist_ok=True)
                cfg_file = cfg_dir / "auth.json"
                existing = {}
                if cfg_file.exists():
                    try:
                        existing = json.loads(cfg_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                existing.update({"api_key": self.api_key.strip()})
                payload = json.dumps(existing, indent=2)
                tmp_fd, tmp_path = tempfile.mkstemp(
                    prefix=".auth.json.", suffix=".tmp", dir=str(cfg_dir),
                )
                try:
                    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                        f.write(payload)
                        f.flush()
                        try:
                            os.fsync(f.fileno())
                        except OSError:
                            pass
                    os.replace(tmp_path, cfg_file)
                except Exception:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise

            exe_path = self._find_exe()
            if exe_path:
                # Desktop + Start menu shortcuts use the DISPLAY name so
                # Windows Explorer reads "Happy AI Agent" instead of
                # "HappyAIAgent". Old installs had `HappyAIAgent.lnk` —
                # uninstall.bat removes both filenames to clean up.
                if self.create_desktop_shortcut:
                    if progress_cb:
                        progress_cb(89, "สร้าง Desktop shortcut...")
                    self._create_shortcut(
                        exe_path,
                        Path.home() / "Desktop" / f"{APP_DISPLAY_NAME}.lnk",
                    )
                    # Also remove the legacy no-space shortcut so users
                    # upgrading from v2.3.3 don't end up with both.
                    legacy = Path.home() / "Desktop" / f"{APP_NAME}.lnk"
                    if legacy.exists():
                        try:
                            legacy.unlink()
                        except OSError:
                            pass
                if self.create_start_menu:
                    if progress_cb:
                        progress_cb(93, "เพิ่มใน Start Menu...")
                    start_menu = (Path(os.environ.get("APPDATA", ""))
                                  / "Microsoft" / "Windows"
                                  / "Start Menu" / "Programs")
                    start_menu.mkdir(parents=True, exist_ok=True)
                    self._create_shortcut(
                        exe_path, start_menu / f"{APP_DISPLAY_NAME}.lnk"
                    )
                    legacy_sm = start_menu / f"{APP_NAME}.lnk"
                    if legacy_sm.exists():
                        try:
                            legacy_sm.unlink()
                        except OSError:
                            pass

            if progress_cb:
                progress_cb(96, "ตั้งค่า uninstaller...")
            uninst_bat = self._write_uninstaller()
            self._register_uninstall(exe_path, uninst_bat)

            if progress_cb:
                progress_cb(100, "เสร็จเรียบร้อย!")
            return True, "Install complete"
        except Exception as e:
            return False, f"Install failed: {e}"

    def _write_uninstaller(self) -> Path:
        assert self.install_dir is not None
        bat = self.install_dir / "uninstall.bat"
        install_dir_str = str(self.install_dir)
        bat.write_text(f"""@echo off
setlocal
echo.
echo  ==========================================
echo   Uninstall {APP_DISPLAY_NAME}
echo  ==========================================
echo.
echo  Install location: {install_dir_str}
echo.
choice /C YN /N /M "  Continue? [Y/N] "
if errorlevel 2 (
    echo  Cancelled.
    timeout /t 2 /nobreak >nul
    exit /b
)
echo.
echo  Closing running app...
taskkill /F /IM {APP_EXE_NAME} >nul 2>&1
echo  Removing shortcuts...
del /Q "%USERPROFILE%\\Desktop\\{APP_NAME}.lnk" >nul 2>&1
del /Q "%USERPROFILE%\\Desktop\\{APP_DISPLAY_NAME}.lnk" >nul 2>&1
del /Q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{APP_NAME}.lnk" >nul 2>&1
del /Q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{APP_DISPLAY_NAME}.lnk" >nul 2>&1
echo  Removing registry entry...
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{REG_KEY_NAME}" /f >nul 2>&1
echo.
choice /C YN /N /M "  Also remove your config (API key + sessions)? [Y/N] "
if errorlevel 2 goto skipcfg
rmdir /S /Q "%USERPROFILE%\\.happy" >nul 2>&1
echo  Config removed.
:skipcfg
echo.
echo  Removing install folder...
REM Spawn detached cmd to delete this folder after we exit
(
echo @echo off
echo timeout /t 2 /nobreak ^>nul
echo rmdir /S /Q "{install_dir_str}"
echo del "%%~f0"
) > "%TEMP%\\happyaiagent_finish.bat"
start "" /B cmd /c "%TEMP%\\happyaiagent_finish.bat"
echo.
echo  Done. Bye!
timeout /t 2 /nobreak >nul
exit
""", encoding="utf-8")
        return bat

    def _register_uninstall(self, exe_path, uninstaller: Path) -> None:
        try:
            import winreg
            assert self.install_dir is not None
            key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{REG_KEY_NAME}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_DISPLAY_NAME)
                winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, "Nick (Happy AI Family)")
                winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, str(self.install_dir))
                winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ,
                                   f'cmd /c "{uninstaller}"')
                if exe_path:
                    winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, str(exe_path))
                winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
        except Exception:
            pass

    def _find_exe(self):
        if not self.install_dir:
            return None
        for p in self.install_dir.rglob(APP_EXE_NAME):
            return p
        return None

    def _versioned_icon_path(self, exe_path: Path) -> Path:
        """Copy `happy_logo.ico` to `happy_logo_v<VERSION>.ico` so the
        Windows shell icon cache treats each install's icon as a new
        file. Without this, the cache keeps showing the old bitmap
        even when the .ico bytes change. (Playbook §"Windows shell
        icon cache" / ENA Desktop v2.6.3 pattern.)

        Returns the versioned path, or the original if copy fails.
        Also cleans up older `happy_logo_v*.ico` siblings so the
        install dir doesn't accumulate dead icons across releases.
        """
        import shutil
        safe_ver = APP_VERSION.replace(".", "_")
        assets_dir = exe_path.parent / "_internal" / "assets"
        original = assets_dir / "happy_logo.ico"
        if not original.exists():
            # Try the un-nested layout (older PyInstaller bundles)
            alt = exe_path.parent / "assets" / "happy_logo.ico"
            if alt.exists():
                original = alt
                assets_dir = exe_path.parent / "assets"
            else:
                return original
        versioned = assets_dir / f"happy_logo_v{safe_ver}.ico"
        if not versioned.exists():
            try:
                shutil.copy2(original, versioned)
            except OSError:
                return original

        # Housekeeping: delete stale `happy_logo_v*.ico` from earlier
        # versions. Keeping them doesn't break anything but adds dead
        # weight after every release.
        try:
            for stale in assets_dir.glob("happy_logo_v*.ico"):
                if stale.name == versioned.name:
                    continue
                try:
                    stale.unlink()
                except OSError:
                    pass
        except Exception:
            pass

        return versioned

    def _create_shortcut(self, target: Path, link: Path) -> None:
        try:
            import pythoncom  # noqa: F401
            from win32com.client import Dispatch
            shell = Dispatch("WScript.Shell")
            sc = shell.CreateShortcut(str(link))
            sc.Targetpath = str(target)
            sc.WorkingDirectory = str(target.parent)
            # Versioned ico forces shell cache miss on each install.
            ico = self._versioned_icon_path(target)
            if ico.exists():
                sc.IconLocation = str(ico)
            sc.Description = APP_DISPLAY_NAME
            sc.Save()
        except Exception:
            bat = link.with_suffix(".bat")
            bat.write_text(f'@echo off\nstart "" "{target}"\n', encoding="utf-8")

        # Nudge Explorer's icon cache (belt-and-braces — versioned
        # filename is the actual fix, but these hints help on some
        # Windows builds).
        self._refresh_shell_icon_cache()

    def _refresh_shell_icon_cache(self) -> None:
        try:
            import ctypes
            from ctypes import wintypes
            shell32 = ctypes.WinDLL("shell32", use_last_error=True)
            # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0
            shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception:
            pass

    def launch_app(self) -> None:
        exe = self._find_exe()
        if exe and exe.exists():
            try:
                os.startfile(str(exe))
            except Exception:
                pass


# ─── Setup window ────────────────────────────────────────────

class SetupWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        # Use ASCII title — bundled Tcl/Tk in frozen mode sometimes drops the
        # Win32 WM_NAME if the string contains certain Unicode chars (em-dash).
        # Display name with space is ASCII-safe.
        self.title(f"{APP_DISPLAY_NAME} Setup v{APP_VERSION}")
        self.geometry("720x560")
        self.minsize(640, 520)
        self.resizable(False, False)

        icon = get_asset("happy_logo.ico")
        if icon:
            try:
                self.iconbitmap(str(icon))
            except Exception:
                pass

        self.installer = Installer()
        self.installer.install_dir = DEFAULT_INSTALL_DIR

        # Mascot — use logo_square (256x256 standalone robot)
        self._mascot_pil = None
        mp = get_asset("happy_logo_square.png")
        if mp:
            try:
                self._mascot_pil = Image.open(mp).convert("RGBA")
            except Exception:
                pass

        self.bg = GradientBackground(self, width=720, height=560)
        self.bg.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        self.card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=14,
                                  border_width=1, border_color=COLOR_CARD_LIGHT)
        self.card.place(relx=0.5, rely=0.5, anchor="center",
                         relwidth=0.88, relheight=0.85)

        self._build_setup_phase()
        self.bg.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Force window to surface + take focus
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _make_mascot(self, size: int):
        if not self._mascot_pil:
            return None
        resized = self._mascot_pil.resize((size, size), Image.LANCZOS)
        return ctk.CTkImage(light_image=resized, dark_image=resized,
                              size=(size, size))

    def _clear_card(self):
        for w in self.card.winfo_children():
            w.destroy()

    def _build_setup_phase(self):
        self._clear_card()
        mascot_img = self._make_mascot(86)
        if mascot_img:
            ctk.CTkLabel(self.card, image=mascot_img, text=""
                          ).pack(pady=(20, 4))
        ctk.CTkLabel(
            self.card, text=f"ยินดีต้อนรับสู่ {APP_DISPLAY_NAME}",
            font=("Segoe UI", 22, "bold"), text_color=COLOR_PRIMARY,
        ).pack(pady=(0, 2))
        ctk.CTkLabel(
            self.card,
            text=f"AI-powered multi-agent code generator  •  v{APP_VERSION}  •  Setup ใช้เวลา 30 วินาที",
            font=("Segoe UI", 11), text_color=COLOR_MUTED,
        ).pack(pady=(0, 14))

        form = ctk.CTkFrame(self.card, fg_color="transparent")
        form.pack(fill="x", padx=40, pady=0)

        # Install location
        ctk.CTkLabel(form, text="ที่ติดตั้ง", font=("Segoe UI", 11, "bold"),
                      text_color=COLOR_TEXT, anchor="w"
                      ).pack(fill="x", pady=(0, 2))
        path_row = ctk.CTkFrame(form, fg_color="transparent")
        path_row.pack(fill="x", pady=(0, 10))
        self.path_var = ctk.StringVar(value=str(DEFAULT_INSTALL_DIR))
        self.path_entry = ctk.CTkEntry(path_row, textvariable=self.path_var, height=32)
        self.path_entry.pack(side="left", fill="x", expand=True)
        enable_paste(self.path_entry)
        ctk.CTkButton(
            path_row, text="Browse", width=80, height=32,
            fg_color=COLOR_CARD_LIGHT, hover_color="#475569",
            command=self._pick_dir,
        ).pack(side="left", padx=(6, 0))

        # API key
        ctk.CTkLabel(form, text="Gemini API key  (ใส่ทีหลังก็ได้)",
                      font=("Segoe UI", 11, "bold"),
                      text_color=COLOR_TEXT, anchor="w"
                      ).pack(fill="x", pady=(0, 2))
        key_row = ctk.CTkFrame(form, fg_color="transparent")
        key_row.pack(fill="x", pady=(0, 10))
        self.key_var = ctk.StringVar()
        self.key_entry = ctk.CTkEntry(key_row, textvariable=self.key_var, height=32,
                                        show="•", placeholder_text="AIzaSy...")
        self.key_entry.pack(side="left", fill="x", expand=True)
        enable_paste(self.key_entry)
        ctk.CTkButton(
            key_row, text="ขอ key ฟรี", width=110, height=32,
            fg_color="transparent", border_color=COLOR_PRIMARY, border_width=1,
            text_color=COLOR_PRIMARY, hover_color=COLOR_CARD_LIGHT,
            command=lambda: webbrowser.open("https://aistudio.google.com/apikey"),
        ).pack(side="left", padx=(6, 0))

        # Checkboxes
        opts = ctk.CTkFrame(form, fg_color="transparent")
        opts.pack(fill="x", pady=(2, 0))
        self.cb_desktop = ctk.CTkCheckBox(opts, text="สร้าง Desktop shortcut")
        self.cb_desktop.select()
        self.cb_desktop.pack(anchor="w", pady=1)
        self.cb_startmenu = ctk.CTkCheckBox(opts, text="เพิ่มใน Start Menu")
        self.cb_startmenu.select()
        self.cb_startmenu.pack(anchor="w", pady=1)
        self.cb_launch = ctk.CTkCheckBox(opts, text="เปิดแอปหลังติดตั้ง")
        self.cb_launch.select()
        self.cb_launch.pack(anchor="w", pady=1)

        # Buttons
        btn_row = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_row.pack(side="bottom", pady=(0, 18))
        ctk.CTkButton(
            btn_row, text="ยกเลิก", width=120, height=40,
            fg_color=COLOR_CARD_LIGHT, hover_color="#475569",
            command=self._on_close,
        ).pack(side="left", padx=4)
        self.install_btn = ctk.CTkButton(
            btn_row, text="✨ ติดตั้ง", width=180, height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=COLOR_PRIMARY, hover_color=COLOR_ACCENT,
            text_color="white",
            command=self._start_install,
        )
        self.install_btn.pack(side="left", padx=4)

    def _pick_dir(self):
        d = filedialog.askdirectory(title="เลือกโฟลเดอร์ติดตั้ง",
                                      initialdir=str(Path.home()))
        if d:
            chosen = Path(d)
            if chosen.name != APP_NAME:
                chosen = chosen / APP_NAME
            self.path_var.set(str(chosen))

    def _start_install(self):
        target = self.path_var.get().strip()
        if not target:
            messagebox.showwarning("ต้องเลือกที่ติดตั้ง",
                                     "กรุณาเลือกโฟลเดอร์ติดตั้ง")
            return
        self.installer.install_dir = Path(target)
        self.installer.api_key = self.key_var.get().strip()
        self.installer.create_desktop_shortcut = bool(self.cb_desktop.get())
        self.installer.create_start_menu = bool(self.cb_startmenu.get())
        self.installer.launch_after = bool(self.cb_launch.get())

        self._build_installing_phase()
        self.after(200, lambda: threading.Thread(
            target=self._install_worker, daemon=True).start())

    def _build_installing_phase(self):
        self._clear_card()
        top = ctk.CTkFrame(self.card, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(18, 10))

        mascot_img = self._make_mascot(56)
        if mascot_img:
            ctk.CTkLabel(top, image=mascot_img, text=""
                          ).pack(side="left", padx=(0, 16))

        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        title_row = ctk.CTkFrame(info, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(title_row, text="กำลังติดตั้ง...",
                      font=("Segoe UI", 18, "bold"),
                      text_color=COLOR_PRIMARY).pack(side="left")
        self.install_pct = ctk.CTkLabel(title_row, text="0%",
                                            font=("Segoe UI", 16, "bold"),
                                            text_color=COLOR_TEXT)
        self.install_pct.pack(side="right")

        self.install_status = ctk.CTkLabel(info, text="เริ่ม...",
                                              font=("Segoe UI", 10),
                                              text_color=COLOR_MUTED, anchor="w")
        self.install_status.pack(fill="x", pady=(2, 6))

        self.install_bar = ctk.CTkProgressBar(info, height=10,
                                                 progress_color=COLOR_PRIMARY)
        self.install_bar.pack(fill="x")
        self.install_bar.set(0)

        ctk.CTkFrame(self.card, height=1, fg_color=COLOR_CARD_LIGHT
                       ).pack(fill="x", padx=20, pady=(4, 8))

        ctk.CTkLabel(self.card, text="📖 ระหว่างรอ — อ่านสักนิด",
                      font=("Segoe UI", 12, "bold"),
                      text_color=COLOR_TEXT, anchor="w"
                      ).pack(fill="x", padx=20, pady=(0, 4))

        text_box = ctk.CTkTextbox(
            self.card, fg_color="#0A1220", text_color="#CBD5E1",
            font=("Consolas", 10), corner_radius=6, wrap="word",
        )
        text_box.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        text_box.insert("end", LICENSE_TEXT)
        text_box.configure(state="disabled")

        self.update_idletasks()

    def _install_worker(self):
        def cb(pct, msg):
            self.after(0, lambda: self._update_progress(pct, msg))
        ok, msg = self.installer.install(progress_cb=cb)
        self.after(0, lambda: self._on_install_done(ok, msg))

    def _update_progress(self, pct: int, msg: str):
        try:
            self.install_bar.set(pct / 100)
            self.install_pct.configure(text=f"{pct}%")
            self.install_status.configure(text=msg)
        except Exception:
            pass

    def _on_install_done(self, ok: bool, msg: str):
        if not ok:
            messagebox.showerror("ติดตั้งไม่สำเร็จ", msg)
            self._build_setup_phase()
            return
        self._build_done_phase()
        if self.installer.launch_after:
            self.after(800, self._launch_and_close)

    def _build_done_phase(self):
        self._clear_card()
        mascot_img = self._make_mascot(100)
        if mascot_img:
            ctk.CTkLabel(self.card, image=mascot_img, text=""
                          ).pack(pady=(36, 12))

        ctk.CTkLabel(self.card, text="เสร็จเรียบร้อย! 🎉",
                      font=("Segoe UI", 26, "bold"),
                      text_color=COLOR_OK).pack(pady=(0, 4))
        ctk.CTkLabel(self.card, text=f"{APP_DISPLAY_NAME} พร้อมใช้งานแล้ว",
                      font=("Segoe UI", 13),
                      text_color=COLOR_MUTED).pack(pady=(0, 12))
        ctk.CTkLabel(self.card,
                      text=f"ติดตั้งที่: {self.installer.install_dir}",
                      font=("Segoe UI", 10), text_color=COLOR_MUTED,
                      wraplength=560, justify="center").pack(pady=(0, 0))

        btn_row = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_row.pack(side="bottom", pady=(0, 24))
        ctk.CTkButton(btn_row, text="ปิด", width=110, height=40,
                       fg_color=COLOR_CARD_LIGHT, hover_color="#475569",
                       command=self._on_close
                       ).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="🚀 เปิด Happy AI Agent", width=180, height=40,
                       font=("Segoe UI", 13, "bold"),
                       fg_color=COLOR_OK, hover_color="#0EA371",
                       command=self._launch_and_close
                       ).pack(side="left", padx=4)

    def _launch_and_close(self):
        self.installer.launch_app()
        self._on_close()

    def _on_close(self):
        try:
            self.bg.stop()
        except Exception:
            pass
        self.destroy()


def _detect_existing_install_dir():
    """Find a prior install location via registry (used by --upgrade)."""
    try:
        import winreg
        key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{REG_KEY_NAME}"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            loc, _ = winreg.QueryValueEx(k, "InstallLocation")
            p = Path(loc)
            if p.exists():
                return p
    except Exception:
        pass
    return None


def _run_silent_upgrade() -> int:
    """Headless install — used by app's auto-updater."""
    print(f"[silent-upgrade] {APP_DISPLAY_NAME} v{APP_VERSION}")
    installer = Installer()
    installer.install_dir = _detect_existing_install_dir() or DEFAULT_INSTALL_DIR
    installer.api_key = ""
    installer.create_desktop_shortcut = True
    installer.create_start_menu = True
    installer.launch_after = True
    print(f"[silent-upgrade] target: {installer.install_dir}")

    try:
        subprocess.run(["taskkill", "/F", "/IM", APP_EXE_NAME],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, timeout=5)
        time.sleep(0.5)
    except Exception:
        pass

    def _cb(pct, msg):
        print(f"[silent-upgrade] {pct:3d}%  {msg}")

    ok, msg = installer.install(progress_cb=_cb)
    if not ok:
        print(f"[silent-upgrade] FAILED: {msg}")
        return 1
    print("[silent-upgrade] OK — relaunching app")
    installer.launch_app()
    return 0


def _setup_crash_log():
    """Frozen --windowed installer can crash silently because stderr is null.
    Mirror happy_native.py's pattern: tee stderr → ~/.happy/installer-crash.log
    so we have breadcrumbs to diagnose silent failures."""
    if not getattr(sys, "frozen", False):
        return
    try:
        log_dir = Path.home() / ".happy"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "installer-crash.log"
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        log_file.write(f"\n=== HappyAIAgent-Setup {APP_VERSION} started at {time.strftime('%Y-%m-%d %H:%M:%S')} (args={sys.argv[1:]}) ===\n")
        sys.stdout = log_file
        sys.stderr = log_file
    except Exception:
        pass


def main() -> int:
    _setup_crash_log()
    try:
        args = sys.argv[1:]
        if "--silent" in args or "--upgrade" in args:
            return _run_silent_upgrade()
        app = SetupWindow()
        app.mainloop()
        return 0
    except Exception:
        import traceback
        try:
            log_dir = Path.home() / ".happy"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "installer-crash.log").open("a", encoding="utf-8").write(
                f"\n!!! INSTALLER CRASH at {time.strftime('%Y-%m-%d %H:%M:%S')}\n{traceback.format_exc()}\n"
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
