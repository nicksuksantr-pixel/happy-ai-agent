"""Paths, VERSION, and constants.

Frozen-aware: when running as a PyInstaller bundle, `APP_ROOT` is the
unpacked `_MEIPASS` temp dir (read-only); when running from source, it's
the project root. User-writable state lives under `USER_DATA`
(`%LOCALAPPDATA%\\Happy-AI-Agent` on Windows, `~/.happy` fallback elsewhere).

Importing this module has no side effects beyond creating `USER_DATA` so
later writes don't race the directory into existence + loading `.env`
into os.environ so updater.py can pick up HAPPY_AI_UPDATE_TOKEN.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Tiny inline KEY=VALUE loader — avoids a python-dotenv dependency.
    Lines starting with # or blank are skipped. Quotes around the value
    are stripped. Existing env vars are NOT overridden so the user can
    still override via shell."""
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


# ─── Roots ────────────────────────────────────────────────────────────────
def _app_root() -> Path:
    """Project root in source mode, `_MEIPASS` in a frozen bundle."""
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        return Path(mp)
    return Path(__file__).resolve().parent.parent


def _user_data_dir() -> Path:
    """Per-user writable state. Used for settings, window geometry,
    sessions, crash logs, and the cached API key."""
    # HAPPY has historically used `~/.happy/` (auth.py and sessions live
    # there). Keep that path stable so existing installs don't lose their
    # API key or run history.
    base = Path.home() / ".happy"
    base.mkdir(parents=True, exist_ok=True)
    return base


APP_ROOT: Path = _app_root()
USER_DATA: Path = _user_data_dir()
ASSETS: Path = APP_ROOT / "assets"

# Load .env from APP_ROOT (or USER_DATA as override) so updater.py +
# auth.py can read HAPPY_AI_UPDATE_TOKEN / other config without forcing
# a python-dotenv dependency.
for _p in (APP_ROOT / ".env", USER_DATA / ".env"):
    _load_env_file(_p)


# ─── Files ────────────────────────────────────────────────────────────────
WINDOW_STATE_PATH: Path = USER_DATA / "window_state.json"
SETTINGS_PATH: Path = USER_DATA / "settings.json"
CRASH_LOG_PATH: Path = USER_DATA / "crash.log"
AUTH_PATH: Path = USER_DATA / "auth.json"  # owned by auth.py
SESSIONS_DIR: Path = USER_DATA / "sessions"

ICON_PATH: Path = ASSETS / "happy_logo.ico"
LOGO_PNG: Path = ASSETS / "happy_logo.png"


# ─── Version (single source of truth — `VERSION` plain-text file) ────────
def app_version() -> str:
    candidates = [APP_ROOT / "VERSION"]
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        candidates.insert(0, Path(mp) / "VERSION")
    for p in candidates:
        try:
            if p.exists():
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v
        except Exception:
            pass
    return "0.0.0"


VERSION: str = app_version()


# ─── Window / app metadata ────────────────────────────────────────────────
APP_NAME = "Happy AI Agent"
APP_TITLE = f"{APP_NAME}  v{VERSION}"
APP_TITLE_PREFIX = APP_NAME  # used by single-instance EnumWindows match
MUTEX_NAME = "Happy-AI-Agent-SingleInstance"
TRAY_TOOLTIP = f"{APP_NAME} v{VERSION}"


# ─── Window geometry defaults ─────────────────────────────────────────────
WINDOW_W = 1360
WINDOW_H = 860
# v2.3.1: lowered from 1100/720 — Nick wanted to compress further. Pages
# now use scrollable wrappers + stack on narrow widths so the layout
# still reads at this size.
MIN_W = 920
MIN_H = 560
SIDEBAR_W = 220


# ─── Free-tier quota reference (from MASTER.md) ───────────────────────────
QUOTA_RPM = 15
QUOTA_TPM = 250_000
QUOTA_RPD = 500


# ─── Pipeline defaults ───────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "model": "gemini-3.1-flash-lite-preview",
    "delay": 45,
    "judge_threshold": 100,
    "max_judge_loops": 5,
    "pipeline_mode": "quick",
}


# ─── Update cadence ───────────────────────────────────────────────────────
UPDATE_CHECK_MS = 3_600_000  # hourly periodic re-poll (playbook §4)


# ─── Convenience for callers ──────────────────────────────────────────────
def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def python_executable() -> str:
    """Where to launch Python for child processes (builder.py uses this)."""
    return sys.executable or "python"


# Touch the env to ensure USER_DATA exists on import.
os.makedirs(USER_DATA, exist_ok=True)
