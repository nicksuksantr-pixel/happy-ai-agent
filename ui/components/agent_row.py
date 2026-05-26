"""Shared `AgentRowWidgets` namedtuple — consistent shape for agent-row
widget bundles in both `running.py` and `done.py`.

v2.8.0 (Cos audit B-12): previously `running.py` stored each agent row as
a 4-tuple `(row, dot, name_btn, extra)` and `done.py` as a 3-tuple
`(row, dot, ph)` — different arity AND different element types (name_btn
is a CTkButton vs ph is the phase dict). Any future refactor that
iterates `_agent_rows` expecting a consistent shape would silently
explode with `IndexError` or `AttributeError`.

This module pins the shape via a typed NamedTuple. Optional fields
default to `None` so a page that doesn't need (say) a score label can
still build a row without inventing a placeholder widget.
"""
from __future__ import annotations

from typing import NamedTuple, Optional, Any


class AgentRowWidgets(NamedTuple):
    """One row in an agent-timeline list.

    Required fields:
        row      — the outer CTkFrame container
        dot      — the colored status dot widget
        name_btn — the CTkButton (or CTkLabel for read-only pages) that
                   shows the phase name; callers read `.cget("text")` or
                   write `.configure(text=...)`.

    Optional fields:
        extra      — a small caption widget for live status (e.g.
                     "running...", "done", judge score). None if the
                     page doesn't surface live progress.
        phase_meta — the phase definition dict (id/name/emoji/etc) from
                     `agents.PHASES`. Useful for read-only pages that
                     want to re-lookup the canonical name later.
    """
    row: Any
    dot: Any
    name_btn: Any
    extra: Optional[Any] = None
    phase_meta: Optional[dict] = None
