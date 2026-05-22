"""JSON read/write helpers + typed accessors for window state and settings.

Best-effort writes (UI state isn't fatal to lose). Reads return a default
when the file is missing or malformed so callers don't need try/except.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core import config


# ─── Low-level helpers ────────────────────────────────────────────────────
def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass  # best-effort — UI state isn't fatal to lose


# ─── Window geometry ──────────────────────────────────────────────────────
def load_window_state() -> dict:
    out = _load_json(config.WINDOW_STATE_PATH, {})
    return out if isinstance(out, dict) else {}


def save_window_state(state: dict) -> None:
    _save_json(config.WINDOW_STATE_PATH, state)


# ─── App settings (model, delay, judge_threshold, mode...) ────────────────
def load_settings() -> dict:
    """Merge user-saved settings on top of DEFAULT_SETTINGS so a missing
    key (older saved file, new default added) doesn't break callers."""
    user = _load_json(config.SETTINGS_PATH, {})
    user = user if isinstance(user, dict) else {}
    merged = dict(config.DEFAULT_SETTINGS)
    for k, v in user.items():
        if k in merged:
            merged[k] = v
    return merged


def save_settings(settings: dict) -> None:
    # Only persist known keys — protects against schema drift.
    keep = {k: settings[k] for k in config.DEFAULT_SETTINGS if k in settings}
    _save_json(config.SETTINGS_PATH, keep)
