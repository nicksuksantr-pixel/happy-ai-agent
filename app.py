"""
HAPPY / AI Agent — Streamlit Web App
"""
import base64
import json
import queue as queue_mod
import threading
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# Streamlit thread context — กัน warning + ทำให้ thread เห็น script context
try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx
except Exception:  # fallback ถ้า version เก่า
    def add_script_run_ctx(thread):
        return thread

from auth import (
    create_client, test_connection, list_available_models,
    save_api_key, load_api_key, clear_api_key, is_valid_key_format,
)
from agents import PHASES, KICKOFF_PHASES, get_phases_for_mode
from file_loader import (
    is_supported, get_file_type, load_file_for_gemini,
    save_attachments_to_session, load_attachments_from_session,
    ALL_SUPPORTED,
)
from pipeline import (
    PipelineRunner, create_session, update_meta,
    list_sessions, load_session, delete_session,
    build_combined_txt,
)
from extractor import (
    extract_from_session, build_zip, build_full_export_zip,
)
from builder import build_exe_from_session, find_main_python_file

# ═══════════════════ PAGE CONFIG ═══════════════════
st.set_page_config(
    page_title="HAPPY / AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════ THEME CSS ═══════════════════
THEME_CSS = """
<style>
:root {
  --happy-orange: #FB923C;
  --happy-pink: #EC4899;
  --happy-yellow: #FBBF24;
  --happy-purple: #A855F7;
  --happy-bg: #FFF7ED;
  --happy-card: #FFFFFF;
  --happy-text: #1F2937;
  --happy-muted: #6B7280;
  --happy-border: #FED7AA;
}

/* App background */
.stApp {
    background: linear-gradient(180deg, #FFF7ED 0%, #FFFFFF 60%);
}

/* Hide Streamlit header/footer */
header[data-testid="stHeader"] { background: transparent; }
.stDeployButton { display: none; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* Buttons — main CTA gradient */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #FB923C 0%, #EC4899 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.7rem 1.5rem !important;
    font-weight: 700 !important;
    font-size: 1.05rem !important;
    box-shadow: 0 4px 12px rgba(251, 146, 60, 0.3);
    transition: all 0.2s ease;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(236, 72, 153, 0.4);
}

.stButton > button,
button[kind="secondary"],
button[kind="tertiary"],
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-tertiary"] {
    border-radius: 10px !important;
    border: 1.5px solid var(--happy-border) !important;
    color: var(--happy-text) !important;
    background: white !important;
    background-color: white !important;
    transition: all 0.15s ease;
}
.stButton > button:hover,
button[kind="secondary"]:hover,
button[kind="tertiary"]:hover,
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-tertiary"]:hover {
    border-color: var(--happy-orange) !important;
    color: var(--happy-orange) !important;
    background: #FFF7ED !important;
    background-color: #FFF7ED !important;
}
/* ตัวอักษรภายใน button (Streamlit ห่อ text ใน span) */
[data-testid="stBaseButton-secondary"] *,
[data-testid="stBaseButton-tertiary"] *,
button[kind="secondary"] *,
button[kind="tertiary"] * { color: inherit !important; }

/* Text input/area */
.stTextArea textarea, .stTextInput input {
    border-radius: 12px !important;
    border: 2px solid var(--happy-border) !important;
    background: white !important;
    font-size: 1rem !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: var(--happy-orange) !important;
    box-shadow: 0 0 0 3px rgba(251, 146, 60, 0.15) !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFF7ED 0%, #FFEFE0 100%);
}
[data-testid="stSidebar"] .stMarkdown { color: var(--happy-text); }

/* Card-like containers */
.happy-card {
    background: white;
    border: 1.5px solid var(--happy-border);
    border-radius: 16px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

/* Header with logo */
.happy-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem 0 0.5rem 0;
    margin-bottom: 1.5rem;
    border-bottom: 2px solid var(--happy-border);
}
.happy-header img {
    height: 130px;
    width: auto;
}

/* Agent status pill */
.agent-pill {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.55rem 0.85rem;
    border-radius: 10px;
    margin-bottom: 0.4rem;
    font-size: 0.92rem;
    transition: all 0.2s ease;
    cursor: pointer;
    user-select: none;
}
.agent-pill:hover { transform: translateX(2px); }
.agent-pill.pending {
    background: #F3F4F6;
    color: var(--happy-muted);
}
.agent-pill.running {
    background: linear-gradient(90deg, #FED7AA 0%, #FBBF24 100%);
    color: #92400E;
    font-weight: 700;
    animation: pulse 2s ease-in-out infinite;
}
.agent-pill.done {
    background: #DCFCE7;
    color: #166534;
    font-weight: 600;
}
.agent-pill.error {
    background: #FEE2E2;
    color: #991B1B;
    font-weight: 600;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.75; }
}

/* Progress bar (custom) */
.happy-progress {
    height: 12px;
    background: #FED7AA;
    border-radius: 999px;
    overflow: hidden;
    margin: 0.5rem 0;
}
.happy-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #FBBF24 0%, #FB923C 50%, #EC4899 100%);
    border-radius: 999px;
    transition: width 0.4s ease;
}

/* Big headline */
.happy-h1 {
    font-size: 2rem;
    font-weight: 800;
    color: var(--happy-text);
    margin: 0;
}
.happy-h2 {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--happy-orange);
    margin-top: 1.5rem;
    margin-bottom: 0.8rem;
}

/* Status badge */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 600;
}
.status-badge.ok { background: #DCFCE7; color: #166534; }
.status-badge.err { background: #FEE2E2; color: #991B1B; }
.status-badge.wait { background: #FEF3C7; color: #92400E; }

/* History item */
.history-item {
    padding: 0.7rem 0.9rem;
    margin-bottom: 0.5rem;
    background: white;
    border-radius: 10px;
    border: 1px solid var(--happy-border);
    cursor: pointer;
    font-size: 0.88rem;
}
.history-item:hover {
    border-color: var(--happy-orange);
    background: #FFF7ED;
}

/* Code block styling */
pre {
    background: #1F2937 !important;
    border-radius: 10px !important;
    padding: 1rem !important;
}

/* === Radio button dots — สีส้ม HAPPY ทั้ง selected/unselected === */
/* Outer circle */
[data-baseweb="radio"] > div:first-child {
    border-color: #FB923C !important;
    background: white !important;
    background-color: white !important;
}
/* Inner dot — มี class นี้เฉพาะตอน checked (Streamlit toggle) */
[data-baseweb="radio"] > div:first-child > div {
    background: #FB923C !important;
    background-color: #FB923C !important;
}
/* Hover */
[data-baseweb="radio"]:hover > div:first-child {
    border-color: #EC4899 !important;
}
/* === END RADIO === */


/* === FORCE TEXT COLORS (Streamlit 1.30+ compatibility) === */
body, .stApp, .stApp p, .stApp span, .stApp div, .stApp label,
.stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown li,
.stRadio label, .stRadio p,
.stCheckbox label, .stCheckbox p,
.stSelectbox label, .stTextInput label, .stTextArea label,
.stSlider label,
[data-testid="stWidgetLabel"], [data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-baseweb="radio"] *, [data-baseweb="checkbox"] *,
[data-baseweb="select"] * {
    color: #1F2937 !important;
}

[data-testid="stWidgetLabel"] p, .stTooltipIcon {
    color: #4B5563 !important;
}

.stTextArea textarea::placeholder,
.stTextInput input::placeholder {
    color: #9CA3AF !important;
    opacity: 1 !important;
}

.stTextArea textarea, .stTextInput input, .stTextInput input[type="text"] {
    color: #1F2937 !important;
    background: white !important;
}

.stNumberInput input { color: #1F2937 !important; background: white !important; }

.stSelectbox > div > div { color: #1F2937 !important; }

.stSlider [data-baseweb="slider"] * { color: #1F2937 !important; }

small, .stCaption { color: #6B7280 !important; }

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stMarkdown * {
    color: #1F2937 !important;
}
/* Sidebar buttons - white bg + dark text */
[data-testid="stSidebar"] button {
    background: white !important;
    background-color: white !important;
    color: #1F2937 !important;
    border: 1.5px solid #FED7AA !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] button * {
    color: #1F2937 !important;
    background: transparent !important;
}
[data-testid="stSidebar"] button:hover {
    background: #FFF7ED !important;
    background-color: #FFF7ED !important;
    border-color: #FB923C !important;
    color: #FB923C !important;
}
[data-testid="stSidebar"] button:hover * {
    color: #FB923C !important;
}
/* Sidebar expander (ลบทั้งหมด) */
[data-testid="stSidebar"] [data-testid="stExpander"] summary,
[data-testid="stSidebar"] [data-testid="stExpander"] details > summary {
    background: white !important;
    color: #1F2937 !important;
}

.stButton > button[kind="primary"] { color: white !important; }
.stButton > button[kind="primary"] * { color: white !important; }
/* === END FORCE TEXT COLORS === */

/* === DROPDOWN POPOVER (selectbox, listbox) === */
ul[role="listbox"], div[role="listbox"], 
[data-baseweb="popover"], [data-baseweb="popover"] *,
[data-baseweb="menu"], [data-baseweb="menu"] *,
[role="option"], [role="option"] * {
    background-color: white !important;
    color: #1F2937 !important;
}
[role="option"]:hover, [role="option"][aria-selected="true"] {
    background-color: #FFF7ED !important;
    color: #FB923C !important;
}

/* Selectbox closed state */
.stSelectbox [data-baseweb="select"] > div {
    background-color: white !important;
    color: #1F2937 !important;
}
.stSelectbox [data-baseweb="select"] input {
    color: #1F2937 !important;
}

/* File uploader - white background + visible text */
[data-testid="stFileUploaderDropzone"] {
    background: white !important;
    background-color: white !important;
    border: 2px dashed #FED7AA !important;
    border-radius: 12px !important;
}
[data-testid="stFileUploaderDropzone"] section {
    background: white !important;
}
[data-testid="stFileUploader"] section {
    background: white !important;
}
[data-testid="stFileUploader"] * {
    color: #1F2937 !important;
}
[data-testid="stFileUploaderDropzone"] * {
    color: #1F2937 !important;
    background: transparent !important;
}
[data-testid="stFileUploaderDropzone"] button {
    background: #FB923C !important;
    background-color: #FB923C !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
}
[data-testid="stFileUploaderDropzone"] button * {
    color: white !important;
}
[data-testid="stFileUploaderDropzone"] button:hover {
    background: #EC4899 !important;
}
[data-testid="stFileUploaderFile"] {
    background: #FFF7ED !important;
    border: 1px solid #FED7AA !important;
}
[data-testid="stFileUploaderFile"] * { color: #1F2937 !important; }

/* Alerts/warnings */
[data-testid="stAlert"] * { color: #1F2937 !important; }
[data-testid="stNotification"] * { color: #1F2937 !important; }

/* Code blocks — dark bg + syntax highlight colors visible */
.stMarkdown pre,
[data-testid="stMarkdownContainer"] pre,
[data-testid="stCodeBlock"] {
    background: #0F172A !important;
    border-radius: 10px !important;
    padding: 1rem !important;
    border: 1px solid #1E293B !important;
}
/* default text color (when no syntax token) — bright off-white */
.stMarkdown pre code,
[data-testid="stMarkdownContainer"] pre code,
[data-testid="stCodeBlock"] code {
    background: transparent !important;
    padding: 0 !important;
    color: #E2E8F0 !important;
}
/* Syntax highlighting tokens — Prism.js style classes */

/* Inline code (single backtick) — orange pill */
.stMarkdown :not(pre) > code,
[data-testid="stMarkdownContainer"] :not(pre) > code {
    background: #FFF7ED !important;
    color: #EA580C !important;
    padding: 2px 8px !important;
    border-radius: 6px !important;
    border: 1px solid #FED7AA !important;
    font-size: 0.9em !important;
}
/* st.code() copy button — keep visible */
[data-testid="stCodeBlock"] button {
    background: rgba(255,255,255,0.1) !important;
    color: white !important;
}
/* === END === */

/* === DOWNLOAD BUTTONS (Export 3 ปุ่ม) === */
.stDownloadButton > button,
[data-testid="stDownloadButton"] > button {
    background: white !important;
    background-color: white !important;
    color: #1F2937 !important;
    border: 2px solid #FED7AA !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}
.stDownloadButton > button *,
[data-testid="stDownloadButton"] > button * {
    color: #1F2937 !important;
}
.stDownloadButton > button:hover,
[data-testid="stDownloadButton"] > button:hover {
    background: #FFF7ED !important;
    border-color: #FB923C !important;
    color: #FB923C !important;
}
.stDownloadButton > button:hover * {
    color: #FB923C !important;
}
/* === END === */

/* === EXPANDER (ดูโจทย์เดิม) === */
.streamlit-expander, [data-testid="stExpander"] {
    background: white !important;
    border: 1.5px solid #FED7AA !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] details > summary {
    background: #FFF7ED !important;
    color: #1F2937 !important;
    border-radius: 10px 10px 0 0 !important;
}
[data-testid="stExpander"] summary *,
[data-testid="stExpander"] details > summary * {
    color: #1F2937 !important;
}
[data-testid="stExpander"] > details > div {
    background: white !important;
    color: #1F2937 !important;
}
[data-testid="stExpander"] > details > div * {
    color: #1F2937 !important;
}
/* === END === */

/* === CODE BLOCK WRAPPER FIX === */
/* Container ที่ห่อ pre — Streamlit ใช้หลาย wrapper */
.stMarkdown div:has(> pre),
[data-testid="stMarkdownContainer"] div:has(> pre) {
    background: transparent !important;
    padding: 0 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* st.code() container */
[data-testid="stCodeBlock"] {
    background: #0F172A !important;
    border-radius: 10px !important;
}
[data-testid="stCodeBlock"] > div,
[data-testid="stCodeBlock"] pre {
    background: #0F172A !important;
}

/* highlight wrapper (Streamlit's syntax highlight container) */
div.highlight, .highlight {
    background: #0F172A !important;
    border-radius: 10px !important;
}
div.highlight pre, .highlight pre {
    background: #0F172A !important;
    color: #E2E8F0 !important;
}

/* Block container around code */
.element-container:has(.stCodeBlock),
.element-container:has(pre) {
    background: transparent !important;
}

/* Streamlit's modern code block class */
.stCode, .stCode > div, .stCode pre {
    background: #0F172A !important;
    color: #E2E8F0 !important;
    border-radius: 10px !important;
}
/* === END === */

/* === TOOLTIP (help param) === */
[data-baseweb="tooltip"], 
[role="tooltip"],
div[data-baseweb="popover"][data-popover-placement] {
    background: white !important;
    background-color: white !important;
    color: #1F2937 !important;
    border: 1px solid #FED7AA !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
}
[data-baseweb="tooltip"] *, 
[role="tooltip"] *,
[data-baseweb="popover"][data-popover-placement] * {
    color: #1F2937 !important;
    background: transparent !important;
}
/* === END TOOLTIP === */

/* === ST.CODE() BLOCK — proper dark theme === */
[data-testid="stCodeBlock"] {
    background: #0F172A !important;
    border-radius: 10px !important;
    border: 1px solid #1E293B !important;
    padding: 0 !important;
}
[data-testid="stCodeBlock"] > div {
    background: #0F172A !important;
    border-radius: 10px !important;
}
[data-testid="stCodeBlock"] pre {
    background: #0F172A !important;
    color: #E2E8F0 !important;
    padding: 1rem !important;
    margin: 0 !important;
    border-radius: 10px !important;
}
[data-testid="stCodeBlock"] code,
[data-testid="stCodeBlock"] pre code {
    background: transparent !important;
    color: #E2E8F0 !important;
    padding: 0 !important;
}
/* Copy button on st.code() */
[data-testid="stCodeBlock"] button {
    background: rgba(255,255,255,0.08) !important;
    color: #E2E8F0 !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
}
[data-testid="stCodeBlock"] button:hover {
    background: rgba(255,255,255,0.15) !important;
}
/* Pygments tokens inside st.code() */

/* === END CODE === */


/* === SYNTAX HIGHLIGHT — override inline styles ของ react-syntax-highlighter === */
/* react-syntax-highlighter ใช้ inline style บน span — ต้อง override ด้วย !important บน selector ที่ specificity สูงพอ */
[data-testid="stCodeBlock"] pre span,
.stMarkdown pre span {
    /* default text สำหรับ token ที่ไม่ match - off-white */
}

/* Streamlit's syntax highlighter ใช้ "language-xxx" class บน code element + token classes */
/* Pygments fallback classes */
[data-testid="stCodeBlock"] .k,    /* keyword */
[data-testid="stCodeBlock"] .kn,
[data-testid="stCodeBlock"] .kd,
[data-testid="stCodeBlock"] .nt {  /* HTML tag */
    color: #F472B6 !important;
}
[data-testid="stCodeBlock"] .s,    /* string */
[data-testid="stCodeBlock"] .s1,
[data-testid="stCodeBlock"] .s2,
[data-testid="stCodeBlock"] .sd {
    color: #FBBF24 !important;
}
[data-testid="stCodeBlock"] .nf,   /* function name */
[data-testid="stCodeBlock"] .nb,   /* builtin */
[data-testid="stCodeBlock"] .na {  /* attribute */
    color: #60A5FA !important;
}
[data-testid="stCodeBlock"] .mi,   /* integer */
[data-testid="stCodeBlock"] .mf,
[data-testid="stCodeBlock"] .kc {  /* True/False/None */
    color: #34D399 !important;
}
[data-testid="stCodeBlock"] .c,    /* comment */
[data-testid="stCodeBlock"] .c1,
[data-testid="stCodeBlock"] .cm {
    color: #94A3B8 !important;
    font-style: italic;
}
[data-testid="stCodeBlock"] .o,    /* operator */
[data-testid="stCodeBlock"] .p {   /* punctuation */
    color: #CBD5E1 !important;
}
[data-testid="stCodeBlock"] .nc,   /* class name */
[data-testid="stCodeBlock"] .ne {  /* exception */
    color: #A78BFA !important;
}

/* default fallback — ถ้า token ไม่ match อะไรเลย ให้สีอ่อนๆ ที่อ่านได้ */
[data-testid="stCodeBlock"] pre,
[data-testid="stCodeBlock"] code,
[data-testid="stCodeBlock"] pre > code,
.stMarkdown pre code {
    color: #E2E8F0 !important;
}

/* บาง Streamlit version ใช้ react-syntax-highlighter ที่ render เป็น inline style บน span */
/* selectorนี้แรงพอจะ override inline (.stCodeBlock > div > pre > code > span) */
[data-testid="stCodeBlock"] pre > code > span {
    /* ไม่ override สี — ปล่อยให้ react-syntax-highlighter ใช้ทีม dark ของมัน */
}


/* === CODE SYNTAX COLORS - override react-syntax-highlighter inline styles === */
/* react-syntax-highlighter ใช้ inline style="color: rgb(...)" ต้องใช้ attribute selector match สี light theme เดิมแล้วเปลี่ยนเป็น dark colors สดใส */

/* Default text inside code block - off-white */
[data-testid="stCodeBlock"] pre code,
[data-testid="stCodeBlock"] pre code > span:not([style]) {
    color: #E2E8F0 !important;
}

/* keyword (def, class, return, if, for...) - default red/maroon → pink */
[data-testid="stCodeBlock"] span[style*="color:#cf222e"],
[data-testid="stCodeBlock"] span[style*="color: rgb(207, 34, 46)"],
[data-testid="stCodeBlock"] span[style*="color:#a626a4"],
[data-testid="stCodeBlock"] span[style*="color: rgb(166, 38, 164)"],
[data-testid="stCodeBlock"] span[style*="color:#8959a8"] {
    color: #F472B6 !important;
}

/* string ("text") - default green/blue → yellow */
[data-testid="stCodeBlock"] span[style*="color:#0a3069"],
[data-testid="stCodeBlock"] span[style*="color: rgb(10, 48, 105)"],
[data-testid="stCodeBlock"] span[style*="color:#50a14f"],
[data-testid="stCodeBlock"] span[style*="color: rgb(80, 161, 79)"],
[data-testid="stCodeBlock"] span[style*="color:#718c00"] {
    color: #FBBF24 !important;
}

/* function/method name - default purple/blue → blue sky */
[data-testid="stCodeBlock"] span[style*="color:#8250df"],
[data-testid="stCodeBlock"] span[style*="color: rgb(130, 80, 223)"],
[data-testid="stCodeBlock"] span[style*="color:#4078f2"],
[data-testid="stCodeBlock"] span[style*="color: rgb(64, 120, 242)"],
[data-testid="stCodeBlock"] span[style*="color:#4271ae"] {
    color: #60A5FA !important;
}

/* number, boolean, None - default brown/orange → green */
[data-testid="stCodeBlock"] span[style*="color:#953800"],
[data-testid="stCodeBlock"] span[style*="color: rgb(149, 56, 0)"],
[data-testid="stCodeBlock"] span[style*="color:#986801"],
[data-testid="stCodeBlock"] span[style*="color: rgb(152, 104, 1)"],
[data-testid="stCodeBlock"] span[style*="color:#f5871f"] {
    color: #34D399 !important;
}

/* comment - default gray → lighter gray + italic */
[data-testid="stCodeBlock"] span[style*="color:#6e7781"],
[data-testid="stCodeBlock"] span[style*="color: rgb(110, 119, 129)"],
[data-testid="stCodeBlock"] span[style*="color:#a0a1a7"],
[data-testid="stCodeBlock"] span[style*="color:#8e908c"] {
    color: #94A3B8 !important;
    font-style: italic;
}

/* class name - purple */
[data-testid="stCodeBlock"] span[style*="color:#953800"][style*="font-weight"],
[data-testid="stCodeBlock"] span[style*="color:#c18401"],
[data-testid="stCodeBlock"] span[style*="color:#c18401"] {
    color: #A78BFA !important;
}
/* === END === */


/* ═══════════════════════════════════════════════════════════════
   HAPPY CODE BLOCK — Pygments-rendered (smart_render uses .happy-code)
   ใช้สี theme HAPPY ส้ม-ชมพู บน bg slate-900
   ═══════════════════════════════════════════════════════════════ */
.happy-code {
    background: #0F172A !important;
    border-radius: 10px !important;
    border: 1px solid #1E293B !important;
    padding: 1rem 1.1rem !important;
    margin: 0.6rem 0 !important;
    overflow-x: auto !important;
    font-family: ui-monospace, "JetBrains Mono", Consolas, "Courier New", monospace !important;
    font-size: 0.92rem !important;
    line-height: 1.55 !important;
}
.happy-code pre {
    background: transparent !important;
    margin: 0 !important;
    padding: 0 !important;
    color: #E2E8F0 !important;
    white-space: pre !important;
}
.happy-code code,
.happy-code .happy-code-inner {
    background: transparent !important;
    padding: 0 !important;
    color: #E2E8F0 !important;
    white-space: pre !important;
    display: block !important;
    font-family: inherit !important;
}
/* Override inline code highlight ที่ Streamlit ใส่ */
.happy-code code .happy-code-inner span,
.happy-code .happy-code-inner span {
    background: transparent !important;
    border: none !important;
}

/* Pygments tokens — HAPPY palette */
.happy-code .hll { background-color: #1E293B; }
.happy-code .c, .happy-code .ch, .happy-code .cm, .happy-code .cp,
.happy-code .cpf, .happy-code .c1, .happy-code .cs { color: #94A3B8 !important; font-style: italic; }      /* comments */
.happy-code .k, .happy-code .kc, .happy-code .kd, .happy-code .kn,
.happy-code .kp, .happy-code .kr, .happy-code .kt { color: #F472B6 !important; font-weight: 600; }        /* keywords (ชมพู) */
.happy-code .o, .happy-code .ow { color: #FB923C !important; }                                            /* operators (ส้ม) */
.happy-code .p { color: #CBD5E1 !important; }                                                             /* punctuation */
.happy-code .n  { color: #E2E8F0 !important; }                                                            /* generic name */
.happy-code .na { color: #FDBA74 !important; }                                                            /* attribute (ส้มอ่อน) */
.happy-code .nb { color: #60A5FA !important; }                                                            /* builtin */
.happy-code .nc { color: #A78BFA !important; font-weight: 600; }                                          /* class name (ม่วง) */
.happy-code .nd { color: #C084FC !important; }                                                            /* decorator */
.happy-code .ne { color: #F87171 !important; }                                                            /* exception */
.happy-code .nf { color: #60A5FA !important; }                                                            /* function name (ฟ้า) */
.happy-code .nl { color: #FBBF24 !important; }                                                            /* label */
.happy-code .nn { color: #A78BFA !important; }                                                            /* namespace */
.happy-code .nt { color: #F472B6 !important; }                                                            /* HTML/XML tag (ชมพู) */
.happy-code .nv, .happy-code .vc, .happy-code .vg,
.happy-code .vi, .happy-code .vm { color: #FCD34D !important; }                                           /* variable */
.happy-code .s, .happy-code .sa, .happy-code .sb, .happy-code .sc,
.happy-code .dl, .happy-code .sd, .happy-code .s2, .happy-code .se,
.happy-code .sh, .happy-code .si, .happy-code .sx, .happy-code .sr,
.happy-code .s1, .happy-code .ss { color: #FBBF24 !important; }                                            /* strings (เหลือง) */
.happy-code .m, .happy-code .mb, .happy-code .mf, .happy-code .mh,
.happy-code .mi, .happy-code .il, .happy-code .mo { color: #34D399 !important; }                          /* numbers (เขียวมิ้น) */
.happy-code .ld { color: #FBBF24 !important; }
.happy-code .gd { color: #F87171 !important; }                                                            /* diff deleted */
.happy-code .gi { color: #34D399 !important; }                                                            /* diff inserted */
.happy-code .gh, .happy-code .gu { color: #60A5FA !important; font-weight: 600; }                         /* diff headers */
.happy-code .ge { font-style: italic; }
.happy-code .gs { font-weight: bold; }
.happy-code .gr { color: #F87171 !important; }
.happy-code .gt { color: #F87171 !important; }
.happy-code .err { color: #FCA5A5 !important; background: rgba(248,113,113,0.12); }                        /* error */
.happy-code .w { color: #475569; }                                                                         /* whitespace */
/* ═══ END HAPPY CODE ═══ */


/* ═══════════════════════════════════════════════════════════════
   FIX: WHITE/STALE OVERLAY ระหว่าง Streamlit rerun
   Streamlit ใส่ data-stale="true" และลด opacity ขณะ rerun → ดูจอลางๆ
   ═══════════════════════════════════════════════════════════════ */
[data-stale="true"],
.stApp [data-stale="true"],
.element-container[data-stale="true"],
.stMarkdown[data-stale="true"],
[data-testid="stMarkdownContainer"][data-stale="true"],
.stCodeBlock[data-stale="true"],
[data-testid="stCodeBlock"][data-stale="true"],
[data-testid="element-container"][data-stale="true"] {
    opacity: 1 !important;
    transition: none !important;
}

/* ปิด fade transition ตอน rerun */
.stApp, .stApp > div, .main, .block-container,
.element-container, [data-testid="element-container"] {
    transition: opacity 0s !important;
}

/* ซ่อน skeleton/spinner overlay กลางจอ */
[data-testid="stStatusWidget"] { display: none !important; }
.stSpinner { opacity: 0.7 !important; }

/* ซ่อน Streamlit toolbar ทั้งหมด (Deploy button + hamburger menu) */
[data-testid="stToolbar"],
[data-testid="stToolbarActions"],
[data-testid="stDeployButton"],
[data-testid="stMainMenu"],
.stDeployButton,
header[data-testid="stHeader"] { display: none !important; }

/* บางครั้ง Streamlit ใส่ "Made with Streamlit" footer */
footer[data-testid="stFooter"] { display: none !important; }

/* ลด top padding หลังซ่อน header */
.stMain .block-container,
section[data-testid="stMain"] .block-container,
[data-testid="stMainBlockContainer"] { padding-top: 1.5rem !important; }
/* ═══ END OVERLAY FIX ═══ */

</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ═══════════════════ STATE INIT ═══════════════════
def init_state():
    defaults = {
        # auth (Gemini API key)
        "auth_ready": False,
        "client": None,
        "api_key": "",                # current key in memory (อาจ load จาก config)
        "available_models": [],
        # pipeline settings — default ปลอดภัยกับ free tier + คุณภาพสูง
        "model": "gemini-2.5-pro",
        "delay": 60,             # 60 วินาที = ปลอดภัย free tier 15 RPM
        "judge_threshold": 100,  # คะแนนผ่าน = 100/100 (เข้มงวดสุด)
        "max_judge_loops": 5,
        "pipeline_mode": "quick",
        "attached_files": [],
        # current session
        "current_session_path": None,
        "current_outputs": {},
        "current_status": {},
        "current_judge_rounds": [],
        "selected_agent": None,
        "running": False,
        "started_at": None,
        "should_stop": False,
        "error_message": "",
        # ui
        "page": "home",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ═══════════════════ AUTO AUTH ON STARTUP ═══════════════════
def auto_authenticate():
    """โหลด API key จาก ~/.happy/auth.json และสร้าง client อัตโนมัติ"""
    if st.session_state.auth_ready:
        return

    saved_key = load_api_key()
    if not saved_key:
        return  # ไม่มี key — user ต้องเข้า Settings

    client, err = create_client(saved_key)
    if err:
        st.session_state.error_message = f"โหลด key แต่สร้าง client ไม่ได้: {err}"
        return

    st.session_state.client = client
    st.session_state.api_key = saved_key
    st.session_state.auth_ready = True

    # โหลด model list (เงียบๆ)
    try:
        models = list_available_models(client)
        if models:
            st.session_state.available_models = models
            if st.session_state.model not in models:
                st.session_state.model = models[0]
    except Exception:
        pass

auto_authenticate()

# ═══════════════════ HELPERS ═══════════════════
def load_logo_b64():
    """โหลดโลโก้เป็น base64"""
    p = Path("assets/happy_logo.png")
    if p.exists():
        return base64.b64encode(p.read_bytes()).decode()
    return ""

LOGO_B64 = load_logo_b64()

def render_header():
    """Header ของทุกหน้า"""
    if LOGO_B64:
        st.markdown(f"""
        <div class="happy-header">
            <img src="data:image/png;base64,{LOGO_B64}" alt="Happy AI Agent">
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="happy-h1">🤖 HAPPY <span style="color:#6B7280;font-size:1rem">AI AGENT</span></div>', unsafe_allow_html=True)

def render_auth_status_compact():
    """แสดงสถานะการเชื่อมต่อแบบสั้นๆ"""
    if st.session_state.auth_ready:
        # โชว์แค่ 6 ตัวแรก/ท้ายของ key (ไม่เปิดเผยทั้งหมด)
        k = st.session_state.api_key
        masked = f"{k[:6]}...{k[-4:]}" if len(k) > 12 else "***"
        st.markdown(
            f'<div class="status-badge ok">🟢 เชื่อมต่อแล้ว</div> '
            f'<small style="color:#6B7280">key: <code>{masked}</code></small>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="status-badge err">🔴 ยังไม่เชื่อมต่อ</div> '
            '<small style="color:#6B7280">เปิด Settings เพื่อตั้งค่า</small>',
            unsafe_allow_html=True
        )

# ═══════════════════ SIDEBAR ═══════════════════
with st.sidebar:
    if LOGO_B64:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom:1rem;">
            <img src="data:image/png;base64,{LOGO_B64}" style="max-width:80%; height:auto;">
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Navigation
    if st.button("🏠 หน้าหลัก", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()

    if st.button("⚙️ ตั้งค่า", use_container_width=True):
        st.session_state.page = "settings"
        st.rerun()

    # ปุ่มกลับไปหน้างานที่กำลังทำ — ขึ้นเฉพาะตอนมี pipeline รันอยู่จริง
    if st.session_state.get("running") and st.session_state.get("current_session_path"):
        if st.button("📺 ดูงานที่กำลังทำ", use_container_width=True, type="primary"):
            st.session_state.page = "running"
            st.rerun()
    
    st.markdown("---")
    st.markdown("**📜 ประวัติ**")
    
    sessions = list_sessions()
    if not sessions:
        st.markdown('<small style="color:#9CA3AF">ยังไม่มีงาน</small>', unsafe_allow_html=True)
    else:
        for s in sessions[:15]:
            preview = s["task_preview"] or "(ไม่มีโจทย์)"
            status_emoji = "✅" if s["status"] == "completed" else ("⏳" if s["status"] == "running" else "⚠️")

            col_open, col_del = st.columns([5, 1])
            with col_open:
                if st.button(
                    f"{status_emoji} {preview[:40]}...",
                    key=f"hist_{s['name']}",
                    use_container_width=True,
                    help=f"{s['name']} • {s['phases_completed']} phases"
                ):
                    data = load_session(s["path"])
                    st.session_state.current_session_path = s["path"]
                    st.session_state.current_outputs = data["outputs"]
                    st.session_state.page = "done"
                    st.session_state.selected_agent = None
                    st.rerun()
            with col_del:
                # ลบทันที — กดทีเดียวจบ
                if st.button("🗑", key=f"del_{s['name']}", use_container_width=True, help="ลบ session นี้"):
                    delete_session(s["path"])
                    if st.session_state.current_session_path == s["path"]:
                        st.session_state.current_session_path = None
                        st.session_state.page = "home"
                    st.rerun()

        if len(sessions) >= 2:
            with st.expander("🗑 ลบทั้งหมด"):
                if st.button("⚠️ ยืนยันลบทุก session", use_container_width=True):
                    for s in sessions:
                        delete_session(s["path"])
                    st.session_state.current_session_path = None
                    st.session_state.page = "home"
                    st.success("ลบเรียบร้อย")
                    time.sleep(0.5)
                    st.rerun()
    
    st.markdown("---")
    render_auth_status_compact()

# ═══════════════════ PAGE: SETTINGS ═══════════════════
def page_settings():
    render_header()
    st.markdown('<div class="happy-h1">⚙️ ตั้งค่า</div>', unsafe_allow_html=True)

    # 1. AUTHENTICATION — Gemini API key (AI Studio)
    st.markdown('<div class="happy-h2">🔐 เชื่อมต่อ Gemini (AI Studio)</div>', unsafe_allow_html=True)

    if st.session_state.auth_ready:
        k = st.session_state.api_key
        masked = f"{k[:6]}...{k[-4:]}" if len(k) > 12 else "***"
        st.success(f"✅ เชื่อมต่อแล้ว — key: `{masked}`")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔄 ทดสอบใหม่", use_container_width=True):
                with st.spinner("กำลังทดสอบ..."):
                    ok, msg = test_connection(st.session_state.client)
                    if ok: st.success(msg)
                    else: st.error(msg)
        with col_b:
            if st.button("🚪 ล็อกเอาท์ (ลบ key)", use_container_width=True):
                clear_api_key()
                st.session_state.api_key = ""
                st.session_state.client = None
                st.session_state.auth_ready = False
                st.session_state.available_models = []
                st.success("ลบ key เรียบร้อย")
                time.sleep(0.5)
                st.rerun()
    else:
        st.warning("⚠️ ยังไม่ได้เชื่อมต่อ — ทำตาม 3 ขั้นตอนข้างล่าง")

        # ─── In-app guide ───
        st.markdown("""
        <div style="background:#FFF7ED; border:2px solid #FED7AA; border-radius:10px; padding:1rem 1.2rem; margin:0.8rem 0">
        <b>🎯 วิธีล็อกอินด้วย Google (ทำครั้งเดียวจบ — ฟรี!)</b>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown("### 📌 ขั้นที่ 1 — ไปสร้าง API key")
            st.markdown(
                '👉 คลิกลิงก์นี้: <a href="https://aistudio.google.com/apikey" target="_blank" '
                'style="display:inline-block; padding:0.5rem 1rem; background:#FB923C; color:white; '
                'text-decoration:none; border-radius:8px; font-weight:600;">🌐 เปิดหน้า AI Studio</a>',
                unsafe_allow_html=True
            )
            st.caption("เปิด tab ใหม่ → login ด้วย Google ที่นิกใช้")

            st.markdown("### 📌 ขั้นที่ 2 — กดสร้าง key")
            st.markdown("""
            - ที่หน้า AI Studio → คลิกปุ่ม **"+ Create API key"**
            - เลือก project (หรือสร้างใหม่ก็ได้ — ฟรีหมด)
            - กด **Create** → ได้ key ขึ้นต้นด้วย `AIza...`
            - คลิก **Copy** เพื่อ copy key
            """)

            st.markdown("### 📌 ขั้นที่ 3 — paste key มาที่นี่")
            api_key_input = st.text_input(
                "🔑 API Key",
                value="",
                type="password",
                placeholder="AIzaSy... (35+ ตัวอักษร)",
                help="key จะถูกเก็บที่ ~/.happy/auth.json (เฉพาะเครื่องนิก) — ครั้งหน้าเปิด app ไม่ต้องทำซ้ำ"
            )

            if st.button("💾 บันทึก & เชื่อมต่อ", type="primary", use_container_width=True):
                if not api_key_input:
                    st.error("กรุณา paste API key")
                elif not is_valid_key_format(api_key_input):
                    st.error("❌ Format ของ key ไม่ถูกต้อง (ต้องขึ้นต้น `AIza` และยาว 35+ ตัวอักษร)")
                else:
                    with st.spinner("กำลังทดสอบ..."):
                        client, err = create_client(api_key_input)
                        if err:
                            st.error(f"❌ {err}")
                        else:
                            ok, msg = test_connection(client)
                            if ok:
                                # save + state
                                ok_save, save_msg = save_api_key(api_key_input)
                                st.session_state.client = client
                                st.session_state.api_key = api_key_input
                                st.session_state.auth_ready = True
                                try:
                                    models = list_available_models(client)
                                    if models:
                                        st.session_state.available_models = models
                                        if st.session_state.model not in models:
                                            st.session_state.model = models[0]
                                except Exception:
                                    pass
                                if ok_save:
                                    st.success(f"{msg}\n\n💾 บันทึก key แล้ว — ครั้งหน้าเปิด HAPPY ใช้ได้เลย")
                                else:
                                    st.warning(f"{msg}\n\n⚠️ {save_msg} (ใช้ได้ในเซสชั่นนี้)")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(msg)

        with st.expander("ℹ️ ทำไมต้องใช้ API key? คีย์ฟรีรึเปล่า? เก็บที่ไหน?"):
            st.markdown("""
            **Q: ทำไมไม่ใช้ Google login ตรงๆ เหมือน gemini.google.com?**
            - `gemini.google.com` เป็นแอปของ Google เอง ใช้ทางลับภายใน
            - app ภายนอก (HAPPY) ต้องใช้ API key ที่ Google ออกให้ — เป็นมาตรฐาน

            **Q: ฟรีไหม?**
            - ✅ ฟรี! AI Studio API key มี free tier
            - Gemini Pro: ~15 requests/นาที, 1.5M tokens/วัน
            - Gemini Flash: ~60 requests/นาที (เร็ว, ถูก)
            - ใช้เกิน → upgrade เป็น paid tier ได้

            **Q: Key เก็บที่ไหน?**
            - บันทึกที่ `~/.happy/auth.json` ในเครื่องนิก (ไม่ส่งไปไหน)
            - ครั้งหน้าเปิด HAPPY → auto-login

            **Q: ถ้าจะลบ key?**
            - กดปุ่ม "🚪 ล็อกเอาท์" หลังเชื่อมต่อแล้ว
            """)

    st.markdown("---")
    
    # 2. MODEL
    st.markdown('<div class="happy-h2">🤖 AI Model</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        available = st.session_state.available_models or [
            "gemini-3.1-pro-preview", "gemini-3.1-flash-lite",
            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite",
        ]
        if st.session_state.model not in available:
            available = [st.session_state.model] + available
        model = st.selectbox(
            "เลือก Model",
            options=available,
            index=available.index(st.session_state.model) if st.session_state.model in available else 0,
        )
        st.session_state.model = model

    with col2:
        st.write("")
        st.write("")
        if st.button("🔄 รีเฟรช", use_container_width=True, help="ดึงรายชื่อ model ใหม่"):
            if st.session_state.client:
                try:
                    models = list_available_models(st.session_state.client)
                    st.session_state.available_models = models
                    st.success(f"พบ {len(models)} โมเดล")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"ดึงรายชื่อไม่ได้: {str(e)[:100]}")
            else:
                st.warning("ยังไม่ได้เชื่อมต่อ")

    with col3:
        st.write("")
        st.write("")
        if st.button("🧪 ทดสอบ", use_container_width=True, help="ลองส่งข้อความให้ model ตอบจริงๆ"):
            if not st.session_state.client:
                st.warning("ยังไม่ได้เชื่อมต่อ")
            else:
                with st.spinner(f"กำลังทดสอบ {model}..."):
                    try:
                        r = st.session_state.client.models.generate_content(
                            model=model,
                            contents="คุณคือ Gemini พร้อมรับงานจากผู้ใช้แล้วใช่ไหม? ตอบเป็นภาษาไทย 1 ประโยคสั้นๆ ที่ทักทายและยืนยันว่าพร้อม",
                        )
                        reply = (r.text or "").strip()[:300] or "(empty)"
                        st.success(f"✅ `{model}` พร้อมใช้งาน!\n\n💬 น้องตอบ: {reply}")
                    except Exception as e:
                        msg = str(e)
                        if "429" in msg or "rate" in msg.lower() or "resource_exhausted" in msg.lower():
                            st.error(f"❌ ติด rate limit — ลอง model ตัวเล็กกว่า (เช่น flash-lite) หรือรอสักครู่")
                        elif "not found" in msg.lower() or "404" in msg:
                            st.error(f"❌ Model ไม่รองรับ API key นี้ — ลองตัวอื่น")
                        elif "permission" in msg.lower() or "401" in msg:
                            st.error(f"❌ API key ไม่มีสิทธิ์ใช้ model นี้")
                        else:
                            st.error(f"❌ ทดสอบไม่ผ่าน: {msg[:200]}")

    st.markdown(
        '<small style="color:#6B7280">💡 <b>Pro</b> = ฉลาดสุด • <b>Flash</b> = เร็ว ราคาถูก ฟรี tier โควต้าเยอะ</small>',
        unsafe_allow_html=True
    )

    # ─── Rate limits table (free tier) ───
    with st.expander("📊 ดูโควต้า Free tier ของแต่ละ model + เช็ค limit ปัจจุบัน"):
        st.markdown("""
        ⚠️ **Gemini API ไม่ส่งจำนวนที่เหลือกลับมา** → HAPPY ดูแบบ real-time ไม่ได้
        ตารางข้างล่างเป็นค่า **ของ Free tier ตาม Google docs** (อาจเปลี่ยนได้)

        | Model | RPM (ครั้ง/นาที) | TPM (token/นาที) | RPD (ครั้ง/วัน) | เหมาะกับ |
        |---|---|---|---|---|
        | gemini-3.1-pro-preview | ~5 | ~250K | ~25 | ⚠️ น้อยมาก — เทสไม่กี่ครั้ง |
        | gemini-2.5-pro | 5 | 250K | 100 | งานคุณภาพสูง 1-2 รอบ |
        | gemini-2.5-flash | 10 | 250K | 250 | ⭐ งานทั่วไป (แนะนำ) |
        | gemini-2.5-flash-lite | 15 | 250K | 1,000 | งานเยอะๆ ทดลอง |
        | gemini-2.0-flash | 15 | 1M | 200 | งาน token เยอะ |
        | gemini-2.0-flash-lite | 30 | 1M | 200 | งานเร็วๆ |

        **คำแนะนำเลือก model:**
        - 🎯 **โจทย์ใหม่ทดสอบเล่นๆ** → `gemini-2.5-flash-lite` (1,000 ครั้ง/วัน — รันได้ ~90 sessions)
        - 🏆 **อยากได้คุณภาพสูง** → `gemini-2.5-pro` (แต่จะรันได้แค่ ~9 sessions/วัน — pipeline 11 phases)
        - ⚡ **งานเล็กๆ เร็วๆ** → `gemini-2.5-flash` (250 ครั้ง/วัน)

        **ลิมิตจริงเช็คได้ที่นี่** (login Google → เห็น limit + ใช้ไปเท่าไหร่):
        """)
        st.markdown(
            '<a href="https://aistudio.google.com/rate-limit" target="_blank" '
            'style="display:inline-block; padding:0.5rem 1rem; background:#FB923C; color:white; '
            'text-decoration:none; border-radius:8px; font-weight:600;">📊 เปิด AI Studio Dashboard</a>',
            unsafe_allow_html=True
        )
        st.caption("💡 1 session ของ HAPPY = 11-18 phases = 11-18 requests + อาจมี Judge revision เพิ่ม")
    
    st.markdown("---")
    
    # 3. PIPELINE SETTINGS
    st.markdown('<div class="happy-h2">⚡ การทำงาน</div>', unsafe_allow_html=True)
    
    st.markdown("**Pipeline Mode**")
    mode = st.radio(
        "เลือกโหมดการทำงาน:",
        options=["quick", "thorough"],
        format_func=lambda x: {
            "quick": "Quick (11 phases, ~10 นาที) - งานทั่วไป",
            "thorough": "Thorough (18 phases, ~20 นาที) - ประชุมเต็มทีม + อ่านไฟล์",
        }[x],
        index=0 if st.session_state.pipeline_mode == "quick" else 1,
        horizontal=False,
        key="settings_mode"
    )
    st.session_state.pipeline_mode = mode
    st.markdown("---")
    st.session_state.delay = st.slider(
        "⏱ พักระหว่างน้องๆ ทำงาน (วินาที)",
        min_value=1, max_value=120,
        value=st.session_state.delay,
        help="แต่ละ phase ของ AI จะเว้นเวลากันกี่วินาที — "
             "น้อย = ทำงานเร็วแต่เสี่ยงเจอ Google บอก 'ช้าๆ หน่อย!' (rate limit) | "
             "มาก = ปลอดภัย ไม่โดนกัน (แนะนำ 60 วินาทีสำหรับ free tier)"
    )

    st.session_state.judge_threshold = st.slider(
        "⚖️ คะแนนผ่านขั้นต่ำของน้องผู้ตรวจ (/100)",
        min_value=50, max_value=100,
        value=st.session_state.judge_threshold,
        help="น้องผู้ตรวจ (Judge) จะให้คะแนนโค้ดที่น้องๆ ทำมา 0-100 — "
             "ถ้าได้คะแนนถึงเลขนี้ = ผ่าน ใช้งานได้ | "
             "ถ้าไม่ถึง = ส่งกลับให้แก้ใหม่ "
             "(100 = เข้มงวดสุด คุณภาพดีสุด แต่อาจต้องวนแก้หลายรอบ)"
    )

    st.session_state.max_judge_loops = st.slider(
        "🔁 จำนวนรอบสูงสุดที่ยอมให้แก้ไข",
        min_value=1, max_value=10,
        value=st.session_state.max_judge_loops,
        help="ถ้าน้องผู้ตรวจให้คะแนนไม่ผ่าน จะส่งกลับให้แก้ — กี่รอบสูงสุด "
             "ถึงจะยอมแพ้และส่งโค้ดเวอร์ชั่นล่าสุดออกมา "
             "(แนะนำ 5 รอบ — มากเกินอาจเปลือง quota)"
    )

def smart_render(text: str):
    """Render agent output — text เป็น markdown, code block render เองด้วย Pygments
    (เลี่ยง react-syntax-highlighter ของ Streamlit ที่สี inline เพี้ยน)
    """
    import re
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, TextLexer
    from pygments.util import ClassNotFound
    from pygments.formatters import HtmlFormatter

    # nowrap=True → return เฉพาะ <span>...</span> ไม่มี <pre>
    # (เลี่ยง Streamlit markdown escape HTML ภายใน <pre>)
    formatter = HtmlFormatter(nowrap=True)
    parts = re.split(r"(```[\w+\-]*\n.*?\n```)", text, flags=re.DOTALL)
    for part in parts:
        if part.startswith("```"):
            m = re.match(r"```([\w+\-]*)\n(.*?)\n```", part, re.DOTALL)
            if m:
                lang = (m.group(1) or "text").lower()
                code = m.group(2)
                try:
                    lexer = get_lexer_by_name(lang)
                except ClassNotFound:
                    lexer = TextLexer()
                code_html = highlight(code, lexer, formatter).rstrip("\n")
                # wrap ด้วย <div> (ไม่ใช่ <pre>) เพื่อให้ markdown ไม่ escape <span>
                wrapped = f'<div class="happy-code"><code class="happy-code-inner">{code_html}</code></div>'
                st.markdown(wrapped, unsafe_allow_html=True)
            else:
                st.markdown(part)
        elif part.strip():
            st.markdown(part)

# ═══════════════════ PAGE: HOME ═══════════════════
def page_home():
    render_header()
    
    if not st.session_state.auth_ready:
        st.warning("⚠️ ยังไม่ได้เชื่อมต่อ Google Cloud — ไปที่ ⚙️ ตั้งค่า ก่อน")
        if st.button("⚙️ ไปหน้าตั้งค่า", type="primary"):
            st.session_state.page = "settings"
            st.rerun()
        return
    
    st.markdown('<div class="happy-h2">💭 อยากให้น้องช่วยทำอะไร?</div>', unsafe_allow_html=True)
    
    task = st.text_area(
        "พิมพ์โจทย์ที่นี่",
        height=160,
        placeholder="ตัวอย่าง:\nสร้างเครื่องคิดเลขแบบหน้าเว็บไฟล์เดียว (HTML+CSS+JS รวมในไฟล์เดียว) มีปุ่ม 0-9, + - × ÷, =, C ดีไซน์สวย ใช้งานบนมือถือได้",
        label_visibility="collapsed",
    )
    
    # ─── File uploader (Thorough mode only) ───
    if st.session_state.pipeline_mode == "thorough":
        st.markdown("**📎 ไฟล์อ้างอิง (optional)**")
        st.caption("รองรับ: PNG, JPG, PDF, Word, Excel, CSV — น้องจะดูทุกไฟล์ก่อนเริ่มทำงาน")
        
        uploaded_files = st.file_uploader(
            "ลาก-วางไฟล์",
            type=["png", "jpg", "jpeg", "webp", "gif", "pdf", "docx", "xlsx", "csv", "txt", "md"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key="home_file_uploader",
        )
        
        if uploaded_files:
            # convert to (name, bytes) tuples and store in session
            new_files = []
            for f in uploaded_files:
                file_bytes = f.read()
                new_files.append((f.name, file_bytes))
            st.session_state.attached_files = new_files
            
            # show preview of attached files
            for name, data in new_files:
                ftype = get_file_type(name)
                size_kb = len(data) / 1024
                emoji_map = {
                    "image": "🖼", "pdf": "📄", "word": "📝",
                    "excel": "📊", "csv": "📋", "text": "📃"
                }
                emoji = emoji_map.get(ftype, "📎")
                st.markdown(f"&nbsp;&nbsp;{emoji} **{name}** &nbsp;`{size_kb:.1f} KB` &nbsp;({ftype})")
        else:
            st.session_state.attached_files = []
    else:
        # Quick mode — no attachments
        st.session_state.attached_files = []
    
    # Quick info bar
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(f"🤖 `{st.session_state.model}`")
    col2.markdown(f"⏱ {st.session_state.delay}s")
    col3.markdown(f"⚖️ {st.session_state.judge_threshold}/100")
    mode_label = "🚀 Thorough" if st.session_state.pipeline_mode == "thorough" else "⚡ Quick"
    n_files = len(st.session_state.attached_files)
    if n_files > 0:
        col4.markdown(f"{mode_label} • 📎 {n_files} ไฟล์")
    else:
        col4.markdown(f"{mode_label}")
    
    st.markdown("")
    
    if st.button("▶️  ให้น้องช่วยทำ!", type="primary", use_container_width=True):
        if not task.strip():
            st.error("กรุณาใส่โจทย์ก่อนครับ")
        else:
            # สร้าง session
            settings = {
                "delay": st.session_state.delay,
                "judge_threshold": st.session_state.judge_threshold,
                "max_judge_loops": st.session_state.max_judge_loops,
                "mode": st.session_state.pipeline_mode,
            }
            session_path = create_session(task, st.session_state.model, settings)
            
            # บันทึก attachments ลง session folder
            if st.session_state.attached_files:
                save_attachments_to_session(session_path, st.session_state.attached_files)
                # update meta
                from pipeline import update_meta
                update_meta(session_path, has_attachments=True)
            # ล้าง pipeline state เก่า กัน thread/queue เก่าค้าง → write ไฟล์ไปยัง path เก่า → ENOENT
            for _k in ("_pipeline_queue", "_pipeline_thread"):
                if _k in st.session_state:
                    del st.session_state[_k]
            st.session_state.current_session_path = session_path
            st.session_state.current_outputs = {}
            phases_for_mode = get_phases_for_mode(st.session_state.pipeline_mode)
            st.session_state.current_status = {p["id"]: "pending" for p in phases_for_mode}
            st.session_state.current_judge_rounds = []
            st.session_state.selected_agent = None
            st.session_state.running = True
            st.session_state.should_stop = False
            st.session_state.started_at = time.time()
            st.session_state.error_message = ""
            st.session_state.page = "running"
            st.rerun()

# ═══════════════════ PAGE: RUNNING ═══════════════════
def render_agent_pills(status_dict, selected, judge_rounds, mode="quick"):
    """แสดง agent status pills - ตาม mode ที่เลือก"""
    phases = get_phases_for_mode(mode)
    html_parts = []
    for phase in phases:
        pid = phase["id"]
        status = status_dict.get(pid, "pending")
        emoji = phase["emoji"]
        name = phase["name"]
        
        # icon ตาม status
        if status == "done":
            icon = "✅"
            cls = "done"
        elif status == "running":
            icon = "🔄"
            cls = "running"
        elif status == "error":
            icon = "❌"
            cls = "error"
        else:
            icon = "⏸"
            cls = "pending"
        
        # Judge แสดงรอบ
        extra = ""
        if pid == "judge" and judge_rounds:
            last = judge_rounds[-1]
            extra = f" <small>({last[1]} {last[2]}/100)</small>"
        
        html_parts.append(
            f'<div class="agent-pill {cls}">'
            f'{icon} {emoji} <b>{name}</b>{extra}'
            f'</div>'
        )
    return "\n".join(html_parts)

def run_pipeline_in_thread(task: str, session_path: Path, settings: dict,
                          status_queue, model: str, client):
    """รัน pipeline ใน thread แยก — ส่ง update ผ่าน queue"""
    def on_start(phase_id, name, idx):
        status_queue.put(("start", phase_id, name, idx))
    
    def on_complete(phase_id, name, idx, output):
        status_queue.put(("complete", phase_id, name, idx, output))
    
    def on_error(phase_id, name, err):
        status_queue.put(("error", phase_id, name, err))
    
    def on_judge(round_num, decision, score):
        status_queue.put(("judge", round_num, decision, score))
    
    # โหลด attachments จาก session ถ้ามี
    attachments = load_attachments_from_session(session_path)
    
    runner = PipelineRunner(
        client=client,
        model=model,
        delay=settings["delay"],
        judge_threshold=settings["judge_threshold"],
        max_judge_loops=settings["max_judge_loops"],
        mode=settings.get("mode", "quick"),
        attachments=attachments,
        on_phase_start=on_start,
        on_phase_complete=on_complete,
        on_phase_error=on_error,
        on_judge_round=on_judge,
    )
    
    try:
        runner.run(task, session_path)
        status_queue.put(("done",))
    except Exception as e:
        # บัก: status ไม่อัปเดตเมื่อ thread ตาย → UI ค้าง running ตลอด
        try:
            from pipeline import update_meta
            update_meta(session_path, status="failed",
                        failed_at=datetime.now().isoformat(),
                        last_error=str(e)[:300])
        except Exception:
            pass
        status_queue.put(("fatal", str(e)[:300]))

def page_running():
    render_header()
    
    session_path = st.session_state.current_session_path
    if not session_path:
        st.error("ไม่มี session ที่กำลังรัน")
        return
    
    task = (session_path / "00_task.txt").read_text(encoding="utf-8") if (session_path / "00_task.txt").exists() else ""
    
    # โจทย์ย่อ
    with st.expander("📋 ดูโจทย์"):
        st.write(task)
    
    # เริ่มรันถ้ายังไม่เริ่ม
    if "_pipeline_queue" not in st.session_state:
        st.session_state._pipeline_queue = queue_mod.Queue()
        # อ่าน mode จาก _meta.json ที่ create_session บันทึกไว้ (กันกรณี user reload หน้า)
        _saved_mode = "quick"
        try:
            _meta = json.loads((session_path / "_meta.json").read_text(encoding="utf-8"))
            _saved_mode = _meta.get("mode", st.session_state.pipeline_mode)
        except Exception:
            _saved_mode = st.session_state.pipeline_mode

        settings = {
            "delay": st.session_state.delay,
            "judge_threshold": st.session_state.judge_threshold,
            "max_judge_loops": st.session_state.max_judge_loops,
            "mode": _saved_mode,
        }
        t = threading.Thread(
            target=run_pipeline_in_thread,
            args=(task, session_path, settings, st.session_state._pipeline_queue,
                  st.session_state.model, st.session_state.client),
            daemon=True
        )
        add_script_run_ctx(t)
        t.start()
        st.session_state._pipeline_thread = t
    
    # ดึง update จาก queue
    q = st.session_state._pipeline_queue
    while not q.empty():
        try:
            msg = q.get_nowait()
        except Exception:
            break
        kind = msg[0]
        if kind == "start":
            _, pid, name, idx = msg
            st.session_state.current_status[pid] = "running"
        elif kind == "complete":
            _, pid, name, idx, output = msg
            st.session_state.current_status[pid] = "done"
            st.session_state.current_outputs[pid] = output
        elif kind == "error":
            _, pid, name, err = msg
            st.session_state.current_status[pid] = "error"
            st.session_state.error_message = err
        elif kind == "judge":
            _, round_num, decision, score = msg
            st.session_state.current_judge_rounds.append((round_num, decision, score))
        elif kind == "done":
            st.session_state.running = False
            st.session_state.page = "done"
            # cleanup
            if "_pipeline_queue" in st.session_state:
                del st.session_state._pipeline_queue
            st.rerun()
        elif kind == "fatal":
            _, err = msg
            st.session_state.error_message = err
            st.session_state.running = False
            if "_pipeline_queue" in st.session_state:
                del st.session_state._pipeline_queue
            st.error(f"❌ Pipeline ผิดพลาด: {err}")
            return
    
    # Layout
    elapsed = int(time.time() - (st.session_state.started_at or time.time()))
    minutes = elapsed // 60
    seconds = elapsed % 60
    
    # ใช้ phases ตาม mode ของ session ที่กำลังรัน (thorough = 18, quick = 11)
    try:
        _mode_now = json.loads((session_path / "_meta.json").read_text(encoding="utf-8")).get("mode", "quick")
    except Exception:
        _mode_now = "quick"
    all_phases = get_phases_for_mode(_mode_now)

    done_count = sum(1 for s in st.session_state.current_status.values() if s == "done")
    total = len(all_phases)
    pct = int(done_count / total * 100) if total else 0
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"""
        <div class="happy-card">
            <b>⏱ ทำงานไปแล้ว: {minutes:02d}:{seconds:02d}</b> &nbsp;•&nbsp;
            <b>📊 Phase: {done_count} / {total}</b>
            <div class="happy-progress" style="margin-top:0.6rem">
                <div class="happy-progress-fill" style="width:{pct}%"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="happy-card" style="text-align:center"><b>กำลังทำงาน...</b><br><span style="font-size:2rem">🤖</span></div>', unsafe_allow_html=True)
    
    # Two columns: agents + output
    col_l, col_r = st.columns([1, 2])
    
    with col_l:
        st.markdown("### 📋 ทีมงาน")
        # ดึง mode จาก session meta
        from pipeline import load_session
        try:
            _data = load_session(st.session_state.current_session_path)
            _mode = _data["meta"].get("mode", "quick")
        except Exception:
            _mode = "quick"
        st.markdown(
            render_agent_pills(
                st.session_state.current_status,
                st.session_state.selected_agent,
                st.session_state.current_judge_rounds,
                mode=_mode,
            ),
            unsafe_allow_html=True
        )
        
        st.markdown("")
        # dropdown to view output — ใช้ phases ตาม mode (รวม kickoff ของ thorough ด้วย)
        done_agents = [
            p for p in all_phases
            if st.session_state.current_status.get(p["id"]) == "done"
        ]
        if done_agents:
            choice = st.selectbox(
                "ดู output ของ:",
                options=[p["id"] for p in done_agents],
                format_func=lambda pid: next((f"{p['emoji']} {p['name']}" for p in all_phases if p["id"] == pid), pid),
                key="running_agent_select",
            )
            st.session_state.selected_agent = choice

    with col_r:
        sel = st.session_state.selected_agent
        if sel and sel in st.session_state.current_outputs:
            phase = next((p for p in all_phases if p["id"] == sel), None)
            if phase:
                st.markdown(f"### {phase['emoji']} {phase['name']}")
            output = st.session_state.current_outputs[sel]
            smart_render(output)
        else:
            st.markdown("### 📺 รอ output...")
            st.info("รอ agent ตัวแรกทำเสร็จก่อน แล้วเลือกดูได้ที่ฝั่งซ้าย")
    
    # poll for pipeline updates - only if there's still work to do
    pipeline_alive = (
        "_pipeline_queue" in st.session_state 
        and st.session_state.get("running", False)
    )
    if pipeline_alive:
        time.sleep(2)
        st.rerun()
    # else: don't rerun - let user interact normally

# ═══════════════════ PAGE: DONE ═══════════════════
def page_done():
    render_header()
    
    session_path = st.session_state.current_session_path
    if not session_path:
        st.error("ไม่มี session ที่จะแสดง")
        return
    
    # โหลด outputs จากดิสก์ — แต่ cache ตาม path เพื่อไม่โหลดซ้ำตอนกดปุ่ม
    cache_key = f"_loaded_{session_path}"
    if not st.session_state.get(cache_key):
        try:
            data = load_session(session_path)
            st.session_state.current_outputs = data["outputs"]
            st.session_state[cache_key] = True
        except Exception as e:
            st.error(f"โหลด session ไม่ได้: {e}")
            return
    
    task = (session_path / "00_task.txt").read_text(encoding="utf-8") if (session_path / "00_task.txt").exists() else ""
    
    # Status header
    st.success("✅ เสร็จเรียบร้อย! น้องทำงานครบทุก phase แล้ว")
    
    with st.expander("📋 ดูโจทย์เดิม"):
        st.write(task)
    
    # Export buttons
    st.markdown('<div class="happy-h2">📤 ดาวน์โหลดผลงาน</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        try:
            combined_txt = build_combined_txt(session_path)
            st.download_button(
                "📄 ดาวน์โหลด TXT",
                data=combined_txt,
                file_name=f"happy_report_{session_path.name}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"สร้าง TXT ไม่ได้: {e}")
    
    with col2:
        try:
            files = extract_from_session(session_path)
            if files:
                zip_bytes = build_zip(files)
                st.download_button(
                    f"💾 ดาวน์โหลดโค้ด ({len(files)} ไฟล์)",
                    data=zip_bytes,
                    file_name=f"happy_code_{session_path.name}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
            else:
                st.warning("ไม่เจอ code block")
        except Exception as e:
            st.error(f"แยกโค้ดไม่ได้: {e}")
    
    with col3:
        try:
            combined_txt = build_combined_txt(session_path)
            all_zip = build_full_export_zip(session_path, combined_txt)
            st.download_button(
                "📦 ดาวน์โหลดทั้งหมด",
                data=all_zip,
                file_name=f"happy_all_{session_path.name}.zip",
                mime="application/zip",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"สร้าง zip ไม่ได้: {e}")

    # ─── Build .exe section — ถ้า session มีโค้ด Python ───
    try:
        _files = extract_from_session(session_path)
        _main_py = find_main_python_file(_files) if _files else None
    except Exception:
        _main_py = None

    if _main_py:
        st.markdown("---")
        st.markdown('<div class="happy-h2">🔧 Build เป็น .exe (Windows)</div>', unsafe_allow_html=True)
        st.caption(f"📄 จะ build จาก: `{_main_py}` — ใช้เวลา ~30-60 วินาที")

        exe_cache_key = f"_exe_built_{session_path.name}"
        cached = st.session_state.get(exe_cache_key)

        if cached and cached.get("ok"):
            st.success(f"✅ {cached['message']}")
            st.download_button(
                f"⬇️ ดาวน์โหลด {cached['filename']}",
                data=cached["bytes"],
                file_name=cached["filename"],
                mime="application/octet-stream",
                use_container_width=True,
                type="primary",
            )
            if st.button("🔄 Build ใหม่", use_container_width=True):
                del st.session_state[exe_cache_key]
                st.rerun()
        else:
            if cached and not cached.get("ok"):
                st.error(f"❌ {cached['message']}")
            if st.button("🔨 เริ่ม Build .exe", use_container_width=True, type="primary"):
                with st.spinner("กำลัง build...อย่าปิดหน้านี้"):
                    progress = st.empty()
                    def _cb(msg):
                        progress.info(msg)
                    ok, msg, exe_bytes, fname = build_exe_from_session(session_path, progress_cb=_cb)
                    st.session_state[exe_cache_key] = {
                        "ok": ok, "message": msg,
                        "bytes": exe_bytes, "filename": fname,
                    }
                st.rerun()

    st.markdown("---")
    
    # View outputs by agent
    st.markdown('<div class="happy-h2">📺 ดู output แต่ละ agent</div>', unsafe_allow_html=True)
    
    outputs = st.session_state.current_outputs
    agent_options = [p for p in PHASES if p["id"] in outputs]
    
    # also include any debugger_revision_N keys
    extra_keys = [k for k in outputs if k.startswith("debugger_revision")]
    
    if not agent_options and not extra_keys:
        st.warning("ไม่มี output")
    else:
        all_options = [(p["id"], f"{p['emoji']} {p['name']}") for p in agent_options]
        all_options += [(k, f"🔄 {k}") for k in extra_keys]
        
        # ─── FRAGMENT: agent output viewer ───
        # rerun เฉพาะส่วนนี้เมื่อเปลี่ยน dropdown — ไม่ rerun ทั้ง app
        @st.fragment
        def _agent_viewer():
            choice = st.selectbox(
                "เลือก:",
                options=[opt[0] for opt in all_options],
                format_func=lambda x: next((opt[1] for opt in all_options if opt[0] == x), x),
                key="agent_viewer_select",
            )
            if choice and choice in outputs:
                smart_render(outputs[choice])
        _agent_viewer()
    
    st.markdown("---")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🆕 สร้างงานใหม่", type="primary", use_container_width=True):
            # reset
            st.session_state.current_session_path = None
            st.session_state.current_outputs = {}
            st.session_state.current_status = {}
            st.session_state.current_judge_rounds = []
            st.session_state.page = "home"
            st.rerun()
    with col_b:
        if st.button("🗑 ลบ session นี้", use_container_width=True):
            delete_session(session_path)
            st.session_state.current_session_path = None
            st.session_state.current_outputs = {}
            st.session_state.page = "home"
            st.rerun()

# ═══════════════════ ROUTER ═══════════════════
if st.session_state.error_message:
    st.error(st.session_state.error_message)
    st.session_state.error_message = ""

page = st.session_state.page
if page == "settings":
    page_settings()
elif page == "running":
    page_running()
elif page == "done":
    page_done()
else:
    page_home()
