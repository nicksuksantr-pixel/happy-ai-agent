"""Regression guards for the v2.8.0 → v2.8.1 Running-page P0.

Bug: `AgentRowWidgets` became a 5-field NamedTuple (Cos audit B-12) but
`ui/pages/running.py` still destructured it into 4 variables in two loops
(`refresh()` and `_pulse_running_dot()`), raising
`ValueError: too many values to unpack (expected 4)` the instant the
Running page mounted — crashing the core "watch a pipeline run" flow on
EVERY run, and (because the exception escaped `_drain_pipeline_queue`
before it rescheduled the 200 ms ticker) permanently freezing all later
UI updates.

These guards are source-level (no Tk display needed) so they run in CI.
"""
from __future__ import annotations

import re
from pathlib import Path

_UI_PAGES = Path(__file__).resolve().parent.parent / "ui" / "pages"
_COMPONENTS = Path(__file__).resolve().parent.parent / "ui" / "components"


def test_running_page_does_not_4tuple_unpack_agent_rows():
    """`for pid, (a, b, c, d) in self._agent_rows.items()` must NOT come
    back — that's the exact shape that broke on the 5-field NamedTuple."""
    src = (_UI_PAGES / "running.py").read_text(encoding="utf-8")
    bad = re.findall(
        r"for\s+\w+\s*,\s*\(\s*\w+\s*,\s*\w+\s*,\s*\w+\s*,\s*\w+\s*\)\s+"
        r"in\s+self\._agent_rows\.items\(\)",
        src,
    )
    assert not bad, f"4-tuple unpack of _agent_rows is back (P0 regression): {bad}"


def test_agent_row_namedtuple_keeps_all_five_fields():
    """running.py + done.py rely on attribute access
    (`w.row / .dot / .name_btn / .extra / .phase_meta`). If the field set
    changes, those accesses break — keep all five present."""
    src = (_COMPONENTS / "agent_row.py").read_text(encoding="utf-8")
    for field in ("row", "dot", "name_btn", "extra", "phase_meta"):
        assert re.search(rf"^\s*{field}\s*:", src, re.MULTILINE), \
            f"AgentRowWidgets is missing field '{field}'"
