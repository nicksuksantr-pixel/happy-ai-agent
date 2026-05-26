"""Render agent markdown output into a `tk.Text` widget.

Supports # / ## / ### headings, **bold**, `inline code`, and ```fenced```
code blocks with Pygments syntax highlighting. Tuned for the dark theme
(One Dark-ish token colors). Used by Running + Done pages.
"""
from __future__ import annotations

import re
import tkinter as tk
from typing import Tuple

import customtkinter as ctk
from pygments import lex
from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer
from pygments.token import Token
from pygments.util import ClassNotFound

# v2.8.0 (Cos audit B-25): reuse extractor's permissive CODE_BLOCK_RE so
# both the file extractor AND the on-screen renderer agree on what
# constitutes a code block. Previously this module had its own stricter
# regex `r"(```[\w+\-]*\n.*?\n```)"` which rejected blocks that
# `extract_files_from_text` happily picked up — same agent output, two
# different parse results, with no obvious reason.
from extractor import CODE_BLOCK_RE
from ui import theme


PYGMENTS_COLORS = {
    Token.Keyword:             "#c678dd",
    Token.Keyword.Constant:    "#d19a66",
    Token.Keyword.Declaration: "#c678dd",
    Token.Keyword.Namespace:   "#c678dd",
    Token.Name.Class:          "#e5c07b",
    Token.Name.Function:       "#61afef",
    Token.Name.Decorator:      "#61afef",
    Token.Name.Builtin:        "#56b6c2",
    Token.Name.Builtin.Pseudo: "#56b6c2",
    Token.Literal.String:      "#98c379",
    Token.Literal.String.Doc:  "#98c379",
    Token.Literal.Number:      "#d19a66",
    Token.Comment:             "#5c6370",
    Token.Comment.Single:      "#5c6370",
    Token.Operator:            "#abb2bf",
    Token.Punctuation:         "#abb2bf",
    Token.Generic.Heading:     theme.TEXT,
}


def _configure_code_tags(t: tk.Text) -> None:
    for tok, color in PYGMENTS_COLORS.items():
        t.tag_configure(str(tok), foreground=color)


def _insert_highlighted_code(t: tk.Text, code: str, lang_hint: str = "") -> None:
    try:
        lexer = get_lexer_by_name(lang_hint) if lang_hint else TextLexer()
    except ClassNotFound:
        try:
            lexer = guess_lexer(code)
        except Exception:
            lexer = TextLexer()
    try:
        tokens = list(lex(code, lexer))
    except Exception:
        tokens = [(Token.Text, code)]
    for tok_type, val in tokens:
        tt = tok_type
        tag = None
        while tt is not None:
            if tt in PYGMENTS_COLORS:
                tag = str(tt)
                break
            tt = getattr(tt, "parent", None)
        if tag:
            t.insert("end", val, tag)
        else:
            t.insert("end", val)


def render_output_to_textbox(t: tk.Text, content: str) -> None:
    t.configure(state="normal")
    t.delete("1.0", "end")
    _configure_code_tags(t)

    t.tag_configure(
        "h1",
        font=(theme.FAMILY, 14, "bold"),
        foreground=theme.ACCENT,
        spacing1=8, spacing3=4,
    )
    t.tag_configure(
        "h2",
        font=(theme.FAMILY, 12, "bold"),
        foreground=theme.ACCENT_2,
        spacing1=6, spacing3=2,
    )
    t.tag_configure(
        "h3",
        font=(theme.FAMILY, 11, "bold"),
        foreground=theme.TEXT,
        spacing1=4,
    )
    t.tag_configure(
        "bold", font=(theme.FAMILY, 10, "bold"),
        foreground=theme.TEXT,
    )
    t.tag_configure(
        "inline_code",
        font=theme.FONT_CODE_SMALL,
        background=theme.BG_CODE,
        foreground="#e06c75",
    )
    t.tag_configure(
        "code_block_bg",
        background=theme.BG_CODE,
        lmargin1=10, lmargin2=10,
        font=theme.FONT_CODE_SMALL,
        spacing1=4, spacing3=4,
    )

    # v2.8.0 (B-25): use extractor.CODE_BLOCK_RE for split-by-fence so
    # the renderer matches the extractor's grammar. The regex was
    # written with a CAPTURING outer group (lang + content), so
    # `re.split` returns alternating [text, lang, content, text, ...]
    # we re-stitch to the same `["text", "```...```", "text", ...]`
    # shape the rest of this loop expects.
    raw = CODE_BLOCK_RE.split(content)
    parts = []
    i = 0
    while i < len(raw):
        if i + 2 < len(raw) and raw[i + 1] is not None:
            # Text BEFORE block, then the block itself.
            if raw[i]:
                parts.append(raw[i])
            lang = raw[i + 1]
            code = raw[i + 2]
            parts.append(f"```{lang}\n{code}\n```")
            i += 3
        else:
            if raw[i]:
                parts.append(raw[i])
            i += 1
    for part in parts:
        if part.startswith("```"):
            m = re.match(r"```([\w+\-]*)\n(.*?)\n```", part, re.DOTALL)
            if m:
                lang = (m.group(1) or "").lower()
                code = m.group(2)
                t.insert("end", "\n")
                start = t.index("end")
                _insert_highlighted_code(t, code, lang_hint=lang)
                end = t.index("end")
                t.tag_add("code_block_bg", start, end)
                t.insert("end", "\n")
            else:
                t.insert("end", part)
            continue
        for line in part.split("\n"):
            if line.startswith("# "):
                t.insert("end", line[2:] + "\n", "h1")
            elif line.startswith("## "):
                t.insert("end", line[3:] + "\n", "h2")
            elif line.startswith("### "):
                t.insert("end", line[4:] + "\n", "h3")
            else:
                pieces = re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", line)
                for piece in pieces:
                    if (piece.startswith("`") and piece.endswith("`")
                            and len(piece) > 2):
                        t.insert("end", piece[1:-1], "inline_code")
                    elif (piece.startswith("**") and piece.endswith("**")
                            and len(piece) > 4):
                        t.insert("end", piece[2:-2], "bold")
                    else:
                        t.insert("end", piece)
                t.insert("end", "\n")
    t.configure(state="disabled")


def create_output_text(parent) -> Tuple[ctk.CTkFrame, tk.Text]:
    """Build a (wrap, Text) pair pre-styled for the dark theme.

    The wrap frame includes a scrollbar already wired. Caller grids the
    wrap; Text inside is `wrap.text`-style via the returned tuple.
    """
    wrap = ctk.CTkFrame(parent, fg_color="transparent")
    wrap.grid_columnconfigure(0, weight=1)
    wrap.grid_rowconfigure(0, weight=1)

    t = tk.Text(
        wrap, wrap="word",
        font=theme.FONT_BODY,
        bg=theme.BG_INPUT, fg=theme.TEXT_SUB,
        relief="flat", borderwidth=0,
        padx=14, pady=12,
        insertbackground=theme.ACCENT,
        state="disabled",
    )
    t.grid(row=0, column=0, sticky="nsew")

    sb = ctk.CTkScrollbar(
        wrap, command=t.yview,
        button_color=theme.BORDER,
        button_hover_color=theme.BORDER_DIM,
    )
    sb.grid(row=0, column=1, sticky="ns")
    t.configure(yscrollcommand=sb.set)
    return wrap, t
