"""Keyboard + clipboard helpers for CTkEntry / CTkTextbox.

`enable_clipboard_shortcuts(widget)` wires up Ctrl+V/C/X/A via the
underlying Tk widget's raw `<Control-Key>` keycodes (V=86, C=67,
X=88, A=65) instead of relying on `<Control-v>` / `<Control-V>`
keysym bindings. That distinction matters because:

- The CustomTkinter wrapper sometimes intercepts text-style
  shortcuts inconsistently when `show="*"` (password mask) is set.
- On a Thai keyboard layout the V key types `ฝ`. The keysym Tk
  fires is then `ฝ` (or "uXXXX") — NOT "v" — so `<Control-v>`
  bindings silently no-op. Users see "Ctrl+V doesn't paste"
  while they're typing in Thai-language IMEs (which Nick uses
  daily).

Also wires a right-click context menu so the same operations are
always reachable with the mouse.

Adapted from `installer/installer.py:enable_paste()` (proven to work
on Nick's machine with the Thai-keyboard IME).
"""
from __future__ import annotations

import tkinter as tk


KEYCODE_V = 86
KEYCODE_C = 67
KEYCODE_X = 88
KEYCODE_A = 65


def enable_clipboard_shortcuts(widget) -> None:
    """Bind keycode-based Ctrl+V/C/X/A and a right-click menu.

    Safe to call on any CTk widget that wraps a Tk Entry or Text —
    the helper unwraps `_entry` if present. Idempotent in practice
    (rebinding the same callback is harmless).
    """
    target = getattr(widget, "_entry", widget)

    def _is_entry() -> bool:
        # Text widgets need different selection-range arguments.
        return isinstance(target, (tk.Entry,)) or "entry" in str(target).lower()

    def do_paste(_e=None):
        try:
            text = target.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            target.delete("sel.first", "sel.last")
        except Exception:
            pass
        try:
            if _is_entry():
                target.insert("insert", text)
            else:
                target.insert("insert", text)
        except Exception:
            pass
        return "break"

    def do_copy(_e=None):
        try:
            if _is_entry():
                sel = target.selection_get()
            else:
                sel = target.get("sel.first", "sel.last")
            target.clipboard_clear()
            target.clipboard_append(sel)
        except Exception:
            pass
        return "break"

    def do_cut(_e=None):
        try:
            if _is_entry():
                sel = target.selection_get()
            else:
                sel = target.get("sel.first", "sel.last")
            target.clipboard_clear()
            target.clipboard_append(sel)
            target.delete("sel.first", "sel.last")
        except Exception:
            pass
        return "break"

    def do_select_all(_e=None):
        try:
            if _is_entry():
                target.select_range(0, "end")
                target.icursor("end")
            else:
                target.tag_add("sel", "1.0", "end-1c")
        except Exception:
            pass
        return "break"

    def on_ctrl(e):
        kc = getattr(e, "keycode", 0)
        if kc == KEYCODE_V:
            return do_paste()
        if kc == KEYCODE_C:
            return do_copy()
        if kc == KEYCODE_X:
            return do_cut()
        if kc == KEYCODE_A:
            return do_select_all()

    def show_menu(e):
        m = tk.Menu(target, tearoff=0)
        m.add_command(label="Cut", command=do_cut)
        m.add_command(label="Copy", command=do_copy)
        m.add_command(label="Paste", command=do_paste)
        m.add_separator()
        m.add_command(label="Select All", command=do_select_all)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    target.bind("<Control-Key>", on_ctrl, add="+")
    target.bind("<Button-3>", show_menu, add="+")
