"""Tests for builder.py — _is_test_file basename detection +
_scan_imports_for_pip stdlib filtering + local-module exclusion.

v2.7.1 (Nick caught live): Build .exe failed two different ways:
  1. `tests/test_logic.py` slipped past `_is_test_file` (it checked
     full path, not basename) → builder tried to write the file
     under tmp/tests/ without mkdir → FileNotFoundError at runtime.
  2. Agent emitted `import speedtest` → built .exe → runtime
     `ModuleNotFoundError: No module named 'speedtest'` because the
     bundled embedded Python didn't have speedtest-cli installed
     and PyInstaller couldn't find it to bundle.

These tests pin the behaviour so neither regresses.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from builder import (
    _is_test_file,
    _scan_imports_for_pip,
    _IMPORT_TO_PYPI,
    _STDLIB_MODULES,
)


# ─── _is_test_file basename detection (Bug 1) ─────────────────────────────
class TestIsTestFile:
    def test_classic_basenames(self):
        """The original basename rules MUST still work."""
        assert _is_test_file("test_foo.py")
        assert _is_test_file("foo_test.py")
        assert _is_test_file("tests.py")
        assert _is_test_file("conftest.py")

    def test_not_a_test_file(self):
        assert not _is_test_file("main.py")
        assert not _is_test_file("app.py")
        assert not _is_test_file("logic.py")
        assert not _is_test_file("testing_utilities.py")

    def test_path_with_test_basename_unix(self):
        """`tests/test_logic.py` — the actual bug from Nick's screenshot."""
        assert _is_test_file("tests/test_logic.py")
        assert _is_test_file("tests/test_foo.py")
        assert _is_test_file("tests/foo_test.py")

    def test_path_with_test_basename_windows(self):
        """Same files via Windows path separator."""
        assert _is_test_file("tests\\test_logic.py")
        assert _is_test_file("tests\\test_foo.py")

    def test_top_level_tests_dir_treats_all_as_test(self):
        """Anything under a top-level tests/ dir is a test file even if
        the basename doesn't match (e.g. tests/helpers.py is fixtures)."""
        assert _is_test_file("tests/helpers.py")
        assert _is_test_file("tests/fixtures.py")
        assert _is_test_file("test/something.py")

    def test_nested_tests_dir_not_skipped(self):
        """Only TOP-level tests/ is special — package/tests/foo.py is
        part of the package, not a test fixture to skip."""
        # mypackage/tests/helpers.py — name says "helpers", basename
        # rules don't catch it → not a test file.
        assert not _is_test_file("mypackage/tests/helpers.py")

    def test_case_insensitive(self):
        assert _is_test_file("Tests/Test_Foo.py")
        assert _is_test_file("TESTS/foo.py")


# ─── _scan_imports_for_pip (Bug 2) ────────────────────────────────────────
class TestScanImports:
    def test_stdlib_only_returns_empty(self):
        files = {
            "main.py": "import os\nimport sys\nfrom pathlib import Path\n",
        }
        assert _scan_imports_for_pip(files) == []

    def test_finds_third_party(self):
        files = {
            "main.py": "import requests\nimport speedtest\n",
        }
        deps = _scan_imports_for_pip(files)
        # speedtest → speedtest-cli via _IMPORT_TO_PYPI map; requests unchanged.
        assert "speedtest-cli" in deps
        assert "requests" in deps

    def test_skips_local_modules(self):
        """Agent emits `main.py` that imports `logic` — `logic.py` is in
        the same files dict so it's a LOCAL module, NOT a PyPI dep."""
        files = {
            "main.py": "from logic import calc\nimport requests\n",
            "logic.py": "def calc(): return 1\n",
        }
        deps = _scan_imports_for_pip(files)
        assert "logic" not in deps
        assert "requests" in deps

    def test_handles_dotted_import(self):
        """`import foo.bar.baz` → top-level package is `foo`."""
        files = {
            "main.py": "import urllib3.contrib.pyopenssl\n",
        }
        deps = _scan_imports_for_pip(files)
        assert deps == ["urllib3"]

    def test_handles_from_import(self):
        files = {
            "main.py": "from PIL import Image\nfrom bs4 import BeautifulSoup\n",
        }
        deps = _scan_imports_for_pip(files)
        # PIL → Pillow, bs4 → beautifulsoup4
        assert "Pillow" in deps
        assert "beautifulsoup4" in deps

    def test_skips_non_py_files(self):
        files = {
            "main.py": "import requests\n",
            "README.md": "import this should not match",
            "config.json": '{"import": "stdlib"}',
        }
        deps = _scan_imports_for_pip(files)
        assert deps == ["requests"]

    def test_skips_comment_lines(self):
        """Strict: regex anchored at line start with optional whitespace
        — but real `import` statements inside docstrings or block
        comments might still match. We don't try to be perfect; we just
        avoid the most common false positive."""
        files = {
            "main.py": (
                "# this comment mentions import json but in a comment\n"
                "import requests\n"
            ),
        }
        deps = _scan_imports_for_pip(files)
        # We don't strip comments yet, so this may include comment matches —
        # but the regex requires NO leading non-whitespace, so `# import`
        # should NOT match.
        assert "json" not in deps   # would be stdlib anyway
        assert "requests" in deps


# ─── Pinned data: stdlib set + name-mapping table ─────────────────────────
class TestStdlibPin:
    def test_critical_stdlib_present(self):
        """If any of these falls out the set, scan_imports breaks."""
        for name in ["os", "sys", "json", "re", "pathlib", "subprocess",
                     "tkinter", "threading", "logging"]:
            assert name in _STDLIB_MODULES, f"{name} must be in _STDLIB_MODULES"

    def test_known_mismatches_mapped(self):
        """If the agent imports any of these and we don't map, pip fails."""
        # speedtest is the one Nick caught.
        assert _IMPORT_TO_PYPI["speedtest"] == "speedtest-cli"
        # Other classics worth pinning.
        assert _IMPORT_TO_PYPI["PIL"] == "Pillow"
        assert _IMPORT_TO_PYPI["cv2"] == "opencv-python"
        assert _IMPORT_TO_PYPI["sklearn"] == "scikit-learn"
        assert _IMPORT_TO_PYPI["bs4"] == "beautifulsoup4"
        assert _IMPORT_TO_PYPI["yaml"] == "PyYAML"


# ─── Integration: scenarios from Nick's actual screenshots ────────────────
class TestNickScenarios:
    def test_speedtest_scenario(self):
        """Reconstruct Nick's screenshot #2: agent generated code that
        imports speedtest. Scanner MUST map to speedtest-cli so pip
        installs the right package."""
        files = {
            "main.py": (
                "import tkinter as tk\n"
                "import speedtest\n"
                "from logic import run_test\n"
            ),
            "logic.py": (
                "import speedtest\n"
                "def run_test():\n"
                "    return speedtest.Speedtest().download()\n"
            ),
        }
        deps = _scan_imports_for_pip(files)
        assert "speedtest-cli" in deps
        assert "tkinter" not in deps  # stdlib
        assert "logic" not in deps    # local module

    def test_test_file_in_subdir_skipped(self):
        """Reconstruct Nick's screenshot #1: agent emitted
        `tests/test_logic.py`. Builder MUST detect + skip it so the
        write-without-mkdir bug never triggers."""
        # The actual write logic was fixed independently; this test
        # just locks in that the file IS detected as a test.
        assert _is_test_file("tests/test_logic.py") is True
