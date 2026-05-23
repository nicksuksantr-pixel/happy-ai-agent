"""CTkTextbox with placeholder support — like CTkEntry's `placeholder_text`
but for multi-line input.

Why custom: CustomTkinter's CTkTextbox doesn't ship a placeholder feature
(only CTkEntry does). Hardcoded "examples" inserted with
`.insert("1.0", "...")` force the user to manually select-and-delete
every time, which is the kind of paper cut that makes an app feel
unfinished.

Behaviour:
  • Empty + unfocused → placeholder visible in dim color
  • Focused (click / Tab in) → placeholder clears, color switches to
    normal text color
  • Focused but no input → placeholder stays visible until first
    keystroke OR until focus is lost again with no content
  • Unfocused with empty content → placeholder comes back
  • Any user input → placeholder gone; subsequent clears (Ctrl+A,
    Delete) followed by focus-out restore it
"""
from __future__ import annotations

import customtkinter as ctk


class PlaceholderTextbox(ctk.CTkTextbox):
    """Drop-in CTkTextbox replacement with auto show/hide placeholder."""

    def __init__(
        self,
        master,
        *,
        placeholder: str = "",
        placeholder_color: str = "#6b7280",   # neutral gray-500
        text_color: str = "#f1f5f9",          # default slate-100
        **kwargs,
    ) -> None:
        # Reserve our text_color for the post-clear state. CTk also
        # accepts text_color as a kwarg so honor any caller override.
        normal_color = kwargs.pop("text_color", text_color)
        super().__init__(master, text_color=placeholder_color, **kwargs)

        self._ph_text: str = placeholder
        self._ph_color: str = placeholder_color
        self._normal_color: str = normal_color
        self._showing_placeholder: bool = False

        # Seed the placeholder if we have one + the box was created empty.
        if placeholder:
            self._show_placeholder()

        # Bind focus + key handlers. `add="+"` keeps user-bound handlers
        # working if anyone subclasses or rebinds the same events.
        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")
        self.bind("<Key>", self._on_key, add="+")
        # Paste + middle-click paste should also clear the placeholder
        # before the paste runs, otherwise the placeholder text would
        # get prepended in front of the pasted content.
        self.bind("<<Paste>>", self._on_paste, add="+")
        self.bind("<Button-2>", self._on_paste, add="+")

    # ── Public helpers ────────────────────────────────────────────────────
    def get_real_text(self) -> str:
        """Return the user's text, or "" if only the placeholder is shown.

        Callers that submit the textbox content (e.g. Run Pipeline) MUST
        use this instead of `get("1.0", "end")`, otherwise an empty
        textbox would silently submit the placeholder string as the
        user's task.
        """
        if self._showing_placeholder:
            return ""
        return self.get("1.0", "end-1c")

    def set_placeholder(self, text: str) -> None:
        """Change the placeholder text. Visible immediately if the
        textbox is currently empty + unfocused."""
        self._ph_text = text
        if self._showing_placeholder:
            super().delete("1.0", "end")
            super().insert("1.0", text)

    # ── Internals ─────────────────────────────────────────────────────────
    def _show_placeholder(self) -> None:
        try:
            super().delete("1.0", "end")
            super().insert("1.0", self._ph_text)
            self.configure(text_color=self._ph_color)
        except Exception:
            pass
        self._showing_placeholder = True

    def _clear_placeholder(self) -> None:
        if not self._showing_placeholder:
            return
        try:
            super().delete("1.0", "end")
            self.configure(text_color=self._normal_color)
        except Exception:
            pass
        self._showing_placeholder = False

    # Event handlers ----------------------------------------------------
    def _on_focus_in(self, _event=None):
        if self._showing_placeholder:
            self._clear_placeholder()

    def _on_focus_out(self, _event=None):
        # Check the actual content. We use the parent's get() because
        # our own get_real_text() would short-circuit on showing_placeholder.
        try:
            content = super().get("1.0", "end-1c")
        except Exception:
            content = ""
        if not content.strip():
            self._show_placeholder()

    def _on_key(self, event):
        # Filter out modifier-only keypresses (Shift, Ctrl, Alt) and
        # navigation keys that shouldn't clear the placeholder. The
        # heuristic: if the keysym is a printable char OR Backspace/
        # Delete/Return/Tab/space, treat it as input intent.
        ks = getattr(event, "keysym", "")
        if ks in (
            "Shift_L", "Shift_R", "Control_L", "Control_R",
            "Alt_L", "Alt_R", "Meta_L", "Meta_R",
            "Caps_Lock", "Num_Lock", "Scroll_Lock",
            "Up", "Down", "Left", "Right",
            "Home", "End", "Page_Up", "Page_Down",
            "Escape", "F1", "F2", "F3", "F4", "F5", "F6",
            "F7", "F8", "F9", "F10", "F11", "F12",
        ):
            return
        if self._showing_placeholder:
            self._clear_placeholder()

    def _on_paste(self, _event=None):
        if self._showing_placeholder:
            self._clear_placeholder()
        # Don't return "break" — let Tk's default paste handler run.
