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
import warnings
from pathlib import Path
from typing import Optional


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


# ─── Free-tier quota reference ────────────────────────────────────────────
# DEPRECATED constants — kept ONLY for back-compat with third-party
# importers. Internal code MUST go through `core.quotas.get_quota(model)`,
# which returns per-model values (these flat constants are wrong for any
# model other than the default).
#
# v2.5.1: a `__getattr__` module hook emits a DeprecationWarning at the
# first read so accidental new uses get flagged. The values still resolve
# to the legacy default-model numbers so nothing breaks at runtime.
_QUOTA_LEGACY = {
    "QUOTA_RPM": 15,
    "QUOTA_TPM": 250_000,
    "QUOTA_RPD": 500,  # matches gemini-3.1-flash-lite-preview free-tier
}


def __getattr__(name: str):
    if name in _QUOTA_LEGACY:
        warnings.warn(
            f"core.config.{name} is deprecated — use "
            f"`core.quotas.get_quota(model)` for per-model limits instead. "
            f"These flat constants assume the default-model free tier and "
            f"silently lie for any other model.",
            DeprecationWarning, stacklevel=2,
        )
        return _QUOTA_LEGACY[name]
    raise AttributeError(f"module 'core.config' has no attribute {name!r}")


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


def python_executable() -> Optional[str]:
    """Where to launch a real Python interpreter for child processes.

    v2.5.1 (Cos audit B-02): when running as a frozen PyInstaller bundle,
    `sys.executable` is `HappyAIAgent.exe` — NOT a Python interpreter.
    Spawning subprocesses with it produces a recursive HAPPY launch, not
    a python invocation. `builder._find_python_executable()` already
    knows how to locate a real python in frozen mode (py.exe launcher,
    PATH lookup, common install paths, with a smoke-test to reject
    HAPPY-renamed-as-python.exe), so just delegate.

    In source mode, `sys.executable` IS python — fast path returns it
    directly.

    Returns None if no real python interpreter is on the system
    (frozen mode + python not installed). Callers must handle None —
    see `builder.PYTHON_MISSING_SENTINEL` for the conventional response.
    """
    if not is_frozen():
        return sys.executable or "python"
    # Frozen mode — defer to builder's verified lookup. Imported lazily
    # to avoid a config↔builder cycle at module load (builder reads
    # config constants during its own import).
    try:
        from builder import _find_python_executable
        return _find_python_executable()
    except Exception:
        return None


# Touch the env to ensure USER_DATA exists on import.
os.makedirs(USER_DATA, exist_ok=True)
