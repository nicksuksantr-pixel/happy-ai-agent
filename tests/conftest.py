"""Pytest configuration — make project root importable + safety guards.

Pytest in CI runs from the repo root, but `tests/` is a package so
relative imports of `pipeline`, `extractor`, `core.quotas`, etc. don't
work without explicit sys.path setup. This file fixes that for all
tests in this directory.

⚠️ SAFETY: feedback_never_test_against_prod_files.md — tests MUST
NOT touch `~/.happy/` (Nick's real auth.json + sessions live there).
The `safe_user_data` fixture monkeypatches all USER_DATA paths to a
per-test tmp_path; use it on any test that exercises save_*/load_*
helpers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make project root importable BEFORE any HAPPY modules try to load.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture
def safe_user_data(tmp_path, monkeypatch):
    """Redirect every USER_DATA-derived path to a tmp dir so no test
    can accidentally write to Nick's real `~/.happy/auth.json`.

    Use this fixture on tests that exercise `auth.save_api_key`,
    `core.persistence.save_settings`, or any other helper that
    writes under the user-data root by default.

    Returns the tmp_path so the test can assert on what was written.
    """
    fake_root = tmp_path / ".happy"
    fake_root.mkdir()
    # Patch the constants used by auth + persistence.
    import auth
    import core.config as cfg
    monkeypatch.setattr(auth, "CONFIG_DIR", fake_root, raising=True)
    monkeypatch.setattr(auth, "CONFIG_FILE", fake_root / "auth.json", raising=True)
    monkeypatch.setattr(cfg, "USER_DATA", fake_root, raising=True)
    monkeypatch.setattr(cfg, "AUTH_PATH", fake_root / "auth.json", raising=True)
    monkeypatch.setattr(cfg, "SETTINGS_PATH", fake_root / "settings.json", raising=True)
    monkeypatch.setattr(cfg, "WINDOW_STATE_PATH", fake_root / "window_state.json", raising=True)
    monkeypatch.setattr(cfg, "CRASH_LOG_PATH", fake_root / "crash.log", raising=True)
    monkeypatch.setattr(cfg, "SESSIONS_DIR", fake_root / "sessions", raising=True)
    return fake_root
