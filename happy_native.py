"""Happy AI Agent — entry point.

The actual UI lives under `ui/` (see `ui/app.py`). This script:
1. Inserts the project root on `sys.path` so `ui.*` and `core.*` resolve
   inside a PyInstaller frozen bundle.
2. Tees stderr to `~/.happy/crash.log` for frozen --windowed builds
   (where the PyInstaller bootloader swallows stderr — lesson #16).
3. Acquires a Win32 single-instance mutex and brings the existing
   window forward if the user double-launches (playbook §3.2).
4. Hands off to `ui.app.main()`.

Run dev:    python happy_native.py
Build:      pyinstaller HappyAIAgent.spec --noconfirm --clean
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


# ─── Crash log (frozen-only) ──────────────────────────────────────────────
def _setup_crash_log() -> None:
    """Tee stdout+stderr to ~/.happy/crash.log when frozen — without it
    a startup exception turns into PyInstaller's generic "Unhandled
    exception" dialog with no stack trace."""
    if not getattr(sys, "frozen", False):
        return
    try:
        log_dir = Path.home() / ".happy"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "crash.log"
        # v2.8.0 (Cos audit B-21): intentional — this file handle lives
        # for the entire process lifetime so stdout/stderr writes from
        # ANY point in the app's run get teed to crash.log. OS reclaims
        # the descriptor on process exit. NOT a leak; documented behavior.
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        log_file.write(
            f"\n=== Happy AI Agent started at "
            f"{datetime.now().isoformat()} ===\n"
        )
        sys.stdout = log_file
        sys.stderr = log_file
    except Exception:
        pass


# ─── Single-instance Win32 mutex (playbook §3.2) ──────────────────────────
_MUTEX_HANDLE = None
# v2.8.0 (Cos audit B-20): import from core.config so there's a single
# source of truth. Previously these strings were duplicated here AND in
# core/config.py — if one was bumped without the other, the single-instance
# detection or window-title matching would silently desync.
try:
    from core.config import APP_TITLE_PREFIX, MUTEX_NAME
except Exception:
    # Hard fallback so an import error doesn't break the entry point.
    APP_TITLE_PREFIX = "Happy AI Agent"
    MUTEX_NAME = "Happy-AI-Agent-SingleInstance"


def _ensure_single_instance() -> None:
    """Hold a named Win32 mutex. If another instance already owns it,
    raise its window and exit this process. If the mutex pre-existed
    but no live Tk window matches our title (zombie dev python.exe),
    proceed as the first instance."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    global _MUTEX_HANDLE
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    ERROR_ALREADY_EXISTS = 183
    SW_RESTORE = 9

    _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    # CRITICAL: ctypes.get_last_error(), not kernel32.GetLastError().
    # WinDLL(use_last_error=True) stores the error in a ctypes slot.
    if ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
        return

    found = [False]
    Proc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM,
    )

    def _cb(hwnd, _l):
        # Gate on window class "Tk" so Explorer windows showing the
        # install path don't false-match our title prefix.
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if not cls.value.startswith("Tk"):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        t = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, t, n + 1)
        if t.value.startswith(APP_TITLE_PREFIX):
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            found[0] = True
            return False
        return True

    cb = Proc(_cb)
    user32.EnumWindows(cb, 0)
    if found[0]:
        sys.exit(0)
    # Mutex pre-existed but no live window — stale handle from a zombie
    # dev python.exe. Proceed as the first instance.


# ─── Entry ───────────────────────────────────────────────────────────────
def main() -> None:
    _setup_crash_log()
    _ensure_single_instance()
    try:
        from ui.app import main as ui_main
        ui_main()
    except Exception:
        import traceback
        try:
            log_dir = Path.home() / ".happy"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "crash.log").open("a", encoding="utf-8").write(
                f"\n!!! CRASH at {datetime.now().isoformat()}\n"
                f"{traceback.format_exc()}\n"
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
