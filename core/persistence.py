"""JSON read/write helpers + typed accessors for window state and settings.

Best-effort writes (UI state isn't fatal to lose). Reads return a default
when the file is missing or malformed so callers don't need try/except.

Writes are atomic (temp file + fsync + os.replace) — ENA Desktop v2.6.7
pattern — so a crash/power-loss mid-write can't leave half-written JSON.
"""
from __future__ import annotations

import json
import os
import tempfile
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
    """Atomic JSON write: write to a temp file in the same dir, fsync,
    then os.replace onto the target. A crash/power-loss either leaves
    the OLD file intact OR atomically swaps in the new one — never a
    half-written JSON that future loads would treat as corrupt."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        # mkstemp in the same directory so os.replace is atomic on Windows
        # (cross-volume rename would fall back to copy+delete).
        fd, tmp_path = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass  # filesystem may not support fsync (e.g. tmpfs)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up the orphan temp file so we don't litter the dir.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
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
