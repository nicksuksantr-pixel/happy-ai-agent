"""Regression: extract_from_session must pick the HIGHEST debugger
revision round, not the lexically-largest filename.

Bug (audit C-P1a): the revision files are named
`06b_debugger_revision_{round}.md`. The old `sorted(..., reverse=True)`
was a STRING sort, so `..._9.md` sorted above `..._10.md` — meaning a
full 10-round judge loop made Build .exe / Download-zip extract the
round-9 code instead of the final round-10 code.
"""
from __future__ import annotations

from extractor import extract_from_session


def _write(path, name, code_line):
    (path / name).write_text(
        f"### File: main.py\n```python\n{code_line}\n```\n",
        encoding="utf-8",
    )


def test_picks_highest_revision_round_not_lexical(tmp_path):
    # round 9 = OLD code, round 10 = the FINAL code the pipeline judged.
    _write(tmp_path, "06b_debugger_revision_9.md", "print('round 9 OLD')")
    _write(tmp_path, "06b_debugger_revision_10.md", "print('round 10 FINAL')")

    files = extract_from_session(tmp_path)

    assert "main.py" in files
    assert "round 10 FINAL" in files["main.py"], files["main.py"]
    assert "round 9 OLD" not in files["main.py"]


def test_single_revision_still_works(tmp_path):
    _write(tmp_path, "06b_debugger_revision_1.md", "print('only round')")
    files = extract_from_session(tmp_path)
    assert files.get("main.py", "").strip() == "print('only round')"
