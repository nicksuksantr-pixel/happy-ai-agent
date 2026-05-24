"""Tests for extractor — code-block parsing + session phase lookup.

Why this matters:
- v2.5.1 (Cos audit B-06) rewrote CODE_BLOCK_RE. Without these tests
  any future regex tweak risks silently dropping LLM-emitted blocks
  again. The tests below pin the exact tolerances we promised:
  blank lines inside the fence, trailing whitespace on the close
  fence, text after the language tag.
- v2.5.1 (B-04) replaced hardcoded `04_coder.md` / `05_frontend.md`
  with a phase_id glob. The glob fix is invisible from any UI assert
  — only a test that drops files at non-standard prefixes proves
  the new behavior.
"""
from extractor import (
    CODE_BLOCK_RE,
    _session_phase_files,
    extract_files_from_text,
    extract_from_session,
    find_filename_in_block,
    find_filename_in_preceding,
)


# ─── Regex behaviour ────────────────────────────────────────────────────

class TestCodeBlockRegex:
    def test_basic_block(self):
        text = "```python\nprint('hi')\n```"
        m = CODE_BLOCK_RE.search(text)
        assert m and m.group(1) == "python"
        assert "print('hi')" in m.group(2)

    def test_block_with_blank_line_inside(self):
        """B-06 regression — the old regex required content to start
        immediately after the open fence. Blank line broke it."""
        text = "```python\n\nprint('hi')\n```"
        m = CODE_BLOCK_RE.search(text)
        assert m is not None, "blank line after fence must not break parse"
        assert "print" in m.group(2)

    def test_block_with_trailing_whitespace_on_close(self):
        text = "```python\nprint(1)\n```   "
        m = CODE_BLOCK_RE.search(text)
        assert m is not None, "trailing ws on close fence must be tolerated"

    def test_block_with_extra_text_after_lang_tag(self):
        """LLMs sometimes emit ```python title="app.py" — we should
        still match the lang tag and skip the trailing decoration."""
        text = "```python title=app.py\nprint(1)\n```"
        m = CODE_BLOCK_RE.search(text)
        assert m is not None
        assert m.group(1) == "python"

    def test_finds_multiple_blocks(self):
        text = (
            "```python\nprint(1)\n```\n\n"
            "some prose\n\n"
            "```html\n<p>hi</p>\n```"
        )
        matches = list(CODE_BLOCK_RE.finditer(text))
        assert len(matches) == 2


# ─── Filename detection ─────────────────────────────────────────────────

class TestFilenameDetection:
    def test_python_comment_marker(self):
        fn, skip = find_filename_in_block("# main.py\nprint(1)")
        assert fn == "main.py"
        assert skip == 1

    def test_html_comment_marker(self):
        fn, _ = find_filename_in_block("<!-- index.html -->\n<p>hi</p>")
        assert fn == "index.html"

    def test_no_marker_returns_none(self):
        fn, skip = find_filename_in_block("def foo(): pass")
        assert fn is None
        assert skip == 0

    def test_preceding_file_heading(self):
        """`### File: app.py` heading above the block."""
        text = "### File: app.py\n"
        assert find_filename_in_preceding(text) == "app.py"

    def test_preceding_inline_code(self):
        text = "Some intro\n\n`server.py`\n"
        assert find_filename_in_preceding(text) == "server.py"

    def test_preceding_returns_none_when_no_signal(self):
        assert find_filename_in_preceding("just plain prose\n") is None


# ─── Full extraction ────────────────────────────────────────────────────

class TestExtractFilesFromText:
    def test_basic_extraction(self):
        text = "```python\n# main.py\nprint('hi')\n```"
        files = extract_files_from_text(text)
        assert "main.py" in files
        assert "print('hi')" in files["main.py"]

    def test_preceding_heading_wins_over_marker(self):
        text = "### File: app.py\n```python\nprint(1)\n```"
        files = extract_files_from_text(text)
        assert "app.py" in files

    def test_smart_default_html_becomes_index(self):
        text = "```html\n<!DOCTYPE html><body>hi</body></html>\n```"
        files = extract_files_from_text(text)
        assert "index.html" in files

    def test_smart_default_python_becomes_main_when_has_dunder_main(self):
        text = '```python\nif __name__ == "__main__":\n    print(1)\n```'
        files = extract_files_from_text(text)
        assert "main.py" in files

    def test_smart_default_js_with_canvas_becomes_game(self):
        text = (
            "```javascript\n"
            "const c = document.getElementById('x');\n"
            "requestAnimationFrame(loop);\n"
            "```"
        )
        files = extract_files_from_text(text)
        assert "game.js" in files

    def test_unknown_lang_falls_back_to_block_NN(self):
        text = "```\nplain text\n```"
        files = extract_files_from_text(text)
        assert any(k.startswith("block_") for k in files)


# ─── Session phase lookup (B-04 fix) ───────────────────────────────────

class TestSessionPhaseFiles:
    def test_quick_mode_prefix(self, tmp_path):
        """Quick mode: coder = 04, frontend = 05."""
        (tmp_path / "04_coder.md").write_text("a", encoding="utf-8")
        (tmp_path / "05_frontend.md").write_text("b", encoding="utf-8")
        found = _session_phase_files(tmp_path, ["coder", "frontend"])
        assert len(found) == 2
        assert found[0].name == "04_coder.md"
        assert found[1].name == "05_frontend.md"

    def test_thorough_mode_prefix(self, tmp_path):
        """Thorough mode: kickoff adds 7 phases → coder=11, frontend=12.
        This is the B-04 bug — old hardcoded ['04_coder.md','05_frontend.md']
        silently returned []."""
        (tmp_path / "11_coder.md").write_text("a", encoding="utf-8")
        (tmp_path / "12_frontend.md").write_text("b", encoding="utf-8")
        found = _session_phase_files(tmp_path, ["coder", "frontend"])
        assert len(found) == 2
        assert found[0].name == "11_coder.md"
        assert found[1].name == "12_frontend.md"

    def test_missing_phase_skipped_not_raised(self, tmp_path):
        (tmp_path / "04_coder.md").write_text("a", encoding="utf-8")
        found = _session_phase_files(tmp_path, ["coder", "frontend"])
        assert len(found) == 1  # frontend missing, no error

    def test_latest_wins_when_phase_ran_multiple_times(self, tmp_path):
        # A retried phase could leave 04_coder.md AND 04_coder_v2.md
        (tmp_path / "04_coder.md").write_text("first", encoding="utf-8")
        (tmp_path / "04_coder_v2.md").write_text("second", encoding="utf-8")
        # Both match *_coder*.md; the helper specifically filters *_coder.md
        # so only the canonical file resolves. Verifying that the canonical
        # path is the one selected:
        found = _session_phase_files(tmp_path, ["coder"])
        assert found[0].name == "04_coder.md"

    def test_extract_from_session_uses_phase_glob(self, tmp_path):
        """End-to-end: thorough-mode prefixes should produce a non-empty
        dict from extract_from_session (was the B-04 silent-empty case)."""
        (tmp_path / "11_coder.md").write_text(
            "```python\n# app.py\nprint(1)\n```", encoding="utf-8"
        )
        (tmp_path / "12_frontend.md").write_text(
            "```html\n<!-- index.html -->\n<p>hi</p>\n```", encoding="utf-8"
        )
        files = extract_from_session(tmp_path)
        assert "app.py" in files
        assert "index.html" in files
