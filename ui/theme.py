"""Dark theme palette + design tokens.

Dark base distilled from ENA Conquest Desktop v2.6.3 (the playbook's
canonical case study). HAPPY brand orange + pink are layered on top as
accents — solid color, not gradient (cleaner on a dark dashboard).

6-digit hex only: CTk rejects 8-digit (alpha-channel) hex and crashes on
first widget. Stick to solid colors and use background composition for
"transparency."

v2.2.0 adds an explicit 4-px spacing grid (S1..S6) + a bigger BIG_NUMBER
font + an XL font for hero numbers on Stats page. Every page is expected
to compose layouts using ONLY these spacing tokens so multi-resolution
windows stay tidy.
"""
from __future__ import annotations

# ─── Surfaces ──────────────────────────────────────────────────────────────
BG_ROOT = "#0d0e16"        # root window behind everything
BG_SIDEBAR = "#13141d"     # sidebar surface
BG_PAGE = "#16161f"        # main content surface
BG_CARD = "#1f2030"        # cards on the page
BG_CARD_HOVER = "#2a2b3d"  # row hover, button hover on cards
BG_INPUT = "#0f1018"       # text fields, dropdowns
BG_CODE = "#0a0b13"        # code blocks in output viewer
BG_TABLE_ROW_ALT = "#1a1b28"  # zebra-stripe table rows on Runs page

# ─── Text ──────────────────────────────────────────────────────────────────
TEXT = "#fafafa"
TEXT_SUB = "#cbd5e1"
TEXT_MUTED = "#94a3b8"
TEXT_DIM = "#64748b"

# ─── HAPPY brand accents ──────────────────────────────────────────────────
ACCENT = "#FB923C"          # orange — primary CTA, active nav, brand
ACCENT_HOVER = "#F97316"
ACCENT_2 = "#EC4899"        # pink — judge / code blocks / secondary CTA
ACCENT_2_HOVER = "#DB2777"
ACCENT_3 = "#A855F7"        # purple — quota / minor info
ACCENT_4 = "#FBBF24"        # yellow — warnings, attach card

# ─── Status colors ────────────────────────────────────────────────────────
ONLINE = "#22c55e"
SUCCESS = "#10b981"
WARN = "#f59e0b"
OFFLINE = "#ef4444"
INFO = "#3b82f6"

# ─── Borders ───────────────────────────────────────────────────────────────
BORDER = "#2c2d3f"
BORDER_DIM = "#1d1e2c"     # subtle separator
BORDER_ACTIVE = ACCENT      # focus / drag-over only — never idle

# ─── Fonts ─────────────────────────────────────────────────────────────────
FAMILY = "Segoe UI"
FAMILY_MONO = "Consolas"

FONT_TITLE = (FAMILY, 22, "bold")
FONT_HEADING = (FAMILY, 17, "bold")
FONT_SUBHEAD = (FAMILY, 13, "bold")
FONT_LABEL = (FAMILY, 11, "bold")
FONT_BODY = (FAMILY, 11)
FONT_BODY_BOLD = (FAMILY, 11, "bold")
FONT_SMALL = (FAMILY, 10)
FONT_TINY = (FAMILY, 9)
FONT_OVERLINE = (FAMILY, 9, "bold")  # ALL-CAPS labels (SECTION HEADERS)
FONT_BIG_NUMBER = (FAMILY, 22, "bold")
FONT_HERO_NUMBER = (FAMILY, 28, "bold")   # Stats page big numerals (28 fits 4-tile row at 920 px minsize)
FONT_CODE = (FAMILY_MONO, 10)
FONT_CODE_SMALL = (FAMILY_MONO, 9)

# ─── Geometry tokens ──────────────────────────────────────────────────────
RADIUS_CARD = 14
RADIUS_BUTTON = 10
RADIUS_SMALL = 6
RADIUS_PILL = 999

# 4-px spacing grid. Use these EVERYWHERE so layouts align across pages.
S1 = 4
S2 = 8
S3 = 12
S4 = 16
S5 = 24
S6 = 32

# Legacy aliases kept while pages migrate.
PADDING_PAGE = S5
PADDING_CARD = S4
PADDING_FIELD = S3

# ─── Nav active strip ─────────────────────────────────────────────────────
ACTIVE_NAV_BG = "#262738"   # subtle lift, not garish
ACTIVE_NAV_TEXT = ACCENT
