"""
extractor.py — แยก code block จาก output ของ pipeline เป็นไฟล์จริง

ใช้กับ output ที่มี code block markdown เช่น:
    ```python
    # app.py
    ...
    ```

หา filename จาก:
- comment บรรทัดแรกของ block (# app.py, // index.js, <!-- file.html -->)
- header แบบ "# 1. `filename.py`" ก่อน code block
"""
import io
import re
import zipfile
from pathlib import Path
from typing import Optional


# v2.5.1 (Cos audit B-06): old regex `r"```(\w*)\n(.*?)\n```"` rejected
# valid code blocks that LLMs commonly emit:
#   - fences with extra text after the language tag (e.g. "```python title=app.py")
#   - blank lines immediately inside the fence
#   - closing fences with trailing whitespace
# New pattern:
#   - `[^\n]*` after `\w*` — allow any trailing text on the open line
#   - `[\s\S]*?` — match any content including blank lines, lazily
#   - `[ \t]*` before close fence — tolerate trailing whitespace
CODE_BLOCK_RE = re.compile(r"```(\w*)[^\n]*\n([\s\S]*?)\n[ \t]*```")

# patterns สำหรับหา filename ในบรรทัดต้นๆ ของ code block
FILENAME_PATTERNS = [
    # # filename.ext  (Python/shell comment, first line of block)
    re.compile(r"^#\s+([a-zA-Z0-9_./-]+\.\w+)\s*$"),
    # // filename.ext (JS/C comment)
    re.compile(r"^//\s+([a-zA-Z0-9_./-]+\.\w+)\s*$"),
    # <!-- filename.ext --> (HTML comment)
    re.compile(r"^<!--\s+([a-zA-Z0-9_./-]+\.\w+)\s+-->"),
    # /* filename.ext */ (CSS comment)
    re.compile(r"^/\*\s+([a-zA-Z0-9_./-]+\.\w+)\s+\*/"),
    # # 1. `filename.ext`
    re.compile(r"^#\s*\d+\.\s*`([^`]+\.\w+)`"),
]

# Fix Bug 12: patterns สำหรับหา filename ใน markdown heading ก่อน code block
# เช่น "### File: index.html" หรือ "## index.html" หรือ "**index.html**"
PRECEDING_HEADER_PATTERNS = [
    # ### File: filename.ext  (preferred — what Coder/Frontend prompts now ask for)
    re.compile(r"^#{1,6}\s*File\s*:\s*`?([a-zA-Z0-9_./-]+\.\w+)`?\s*$", re.IGNORECASE),
    # ### `filename.ext`
    re.compile(r"^#{1,6}\s*`([a-zA-Z0-9_./-]+\.\w+)`\s*$"),
    # ### filename.ext
    re.compile(r"^#{1,6}\s+([a-zA-Z0-9_./-]+\.\w+)\s*$"),
    # **filename.ext** (bold)
    re.compile(r"^\*\*([a-zA-Z0-9_./-]+\.\w+)\*\*\s*$"),
    # `filename.ext` (inline code, alone on line)
    re.compile(r"^`([a-zA-Z0-9_./-]+\.\w+)`\s*$"),
]

# language → file extension fallback
LANG_EXT = {
    "python": "py", "py": "py",
    "javascript": "js", "js": "js",
    "typescript": "ts", "ts": "ts",
    "html": "html",
    "css": "css",
    "sql": "sql",
    "json": "json",
    "yaml": "yml", "yml": "yml",
    "bash": "sh", "shell": "sh", "sh": "sh",
    "dockerfile": "Dockerfile",
    "ini": "ini",
    "toml": "toml",
    "xml": "xml",
    "java": "java",
    "go": "go",
    "rust": "rs", "rs": "rs",
    "cpp": "cpp", "c++": "cpp",
}


def find_filename_in_block(code: str) -> tuple:
    """หา filename จากบรรทัดต้นๆ ของ code block (in-block markers)
    Returns: (filename or None, lines_to_skip)"""
    lines = code.split("\n")
    for idx in range(min(3, len(lines))):
        line = lines[idx].strip()
        if not line:
            continue
        for pat in FILENAME_PATTERNS:
            m = pat.match(line)
            if m:
                return m.group(1).strip(), idx + 1
    return None, 0


def find_filename_in_preceding(text_before: str) -> str | None:
    """Fix Bug 12: หา filename จาก markdown heading/marker ก่อน code block
    เช่น '### File: index.html' บรรทัดก่อน ```html ```"""
    if not text_before:
        return None
    # Take last 6 non-empty lines before the block (closest first)
    lines = [l.strip() for l in text_before.rstrip().split("\n") if l.strip()][-6:]
    for line in reversed(lines):
        for pat in PRECEDING_HEADER_PATTERNS:
            m = pat.match(line)
            if m:
                return m.group(1).strip()
    return None


def _smart_default_filename(lang: str, code: str, existing: dict) -> str | None:
    """Fix Bug 12: เดาชื่อไฟล์จาก lang + content ก่อน fallback เป็น block_NN
    คืน None ถ้าเดาไม่ออก (เพื่อให้ caller fallback block_NN)"""
    code_l = code.lower()

    # HTML → index.html ถ้ายังไม่มี (web app entry)
    if lang in ("html", "htm"):
        if "index.html" not in existing:
            return "index.html"

    # JS/TS → game.js ถ้ามี canvas/game keyword, ไม่งั้น app.js
    if lang in ("javascript", "js", "typescript", "ts"):
        is_game = ("canvas" in code_l or "requestanimationframe" in code_l
                   or "gameloop" in code_l or "ctx.fillrect" in code_l)
        preferred = "game.js" if is_game else "app.js"
        if preferred not in existing:
            return preferred

    # CSS → style.css
    if lang == "css":
        if "style.css" not in existing:
            return "style.css"

    # Python → main.py ถ้ามี if __name__, ไม่งั้น app.py
    if lang in ("python", "py"):
        if "if __name__" in code or "__main__" in code:
            if "main.py" not in existing:
                return "main.py"
        if "app.py" not in existing:
            return "app.py"

    return None  # caller จะใช้ block_NN


def extract_files_from_text(text: str) -> dict:
    """หา code block ทั้งหมด → คืน {filename: content}
    Priority หา filename:
      1. heading ก่อน block: '### File: index.html' (Bug 12 fix)
      2. comment marker บรรทัดแรกใน block: '# foo.py', '// foo.js', '<!-- foo.html -->'
      3. smart default ตาม lang+content: 'index.html', 'game.js', 'main.py'
      4. fallback: 'block_NN.<ext>'"""
    files = {}
    unnamed_counter = 1
    last_end = 0

    for match in CODE_BLOCK_RE.finditer(text):
        text_before = text[last_end:match.start()]
        lang = match.group(1).lower()
        code = match.group(2)
        last_end = match.end()

        # Priority 1: heading ก่อน block
        filename = find_filename_in_preceding(text_before)
        skip = 0
        # Priority 2: marker ใน block
        if not filename:
            filename, skip = find_filename_in_block(code)
        actual_code = "\n".join(code.split("\n")[skip:]).strip()

        if not actual_code:
            continue

        # Priority 3: smart default
        if not filename:
            filename = _smart_default_filename(lang, code, files)
        # Priority 4: block_NN fallback
        if not filename:
            ext = LANG_EXT.get(lang, "txt")
            filename = f"block_{unnamed_counter:02d}.{ext}"
            unnamed_counter += 1

        # ถ้าซ้ำ เอาก้อนใหญ่กว่า (น่าจะเป็น final version)
        if filename in files:
            if len(actual_code) > len(files[filename]):
                files[filename] = actual_code
        else:
            files[filename] = actual_code

    return files


def _session_phase_files(session_path: Path, phase_ids: list) -> list:
    """Locate saved phase outputs by phase_id, regardless of numeric prefix.

    v2.5.1 (Cos audit B-04): the previous hardcoded `["04_coder.md",
    "05_frontend.md"]` lookup was wrong in **thorough mode** — KICKOFF_PHASES
    adds 7 phases at the front, so coder lands at `11_coder.md` and frontend
    at `12_frontend.md`. Old code silently returned `{}` for thorough runs.

    Strategy: glob `*_<phase_id>.md` so any prefix shift caused by adding
    or reordering KICKOFF / IMPL phases keeps working without source edits.
    """
    found = []
    for pid in phase_ids:
        # Highest-numbered file wins if there are duplicates (e.g. a phase
        # ran twice — caller typically wants the latest pass).
        matches = sorted(session_path.glob(f"*_{pid}.md"))
        if matches:
            found.append(matches[-1])
    return found


def extract_from_session(session_path: Path) -> dict:
    """
    ดึงโค้ดจาก session — ลำดับความสำคัญ:
    1. debugger_revision (ล่าสุด) — code หลัง Judge แก้
    2. debugger — code หลัง Debugger ครั้งแรก
    3. coder + frontend — รวมจาก 2 phase (resolved by phase_id, not by
       hardcoded numeric prefix)
    """
    # ลองหา debugger revision ล่าสุด
    revisions = sorted([
        f for f in session_path.iterdir()
        if f.suffix == ".md" and "debugger_revision" in f.name
    ], reverse=True)

    if revisions:
        text = revisions[0].read_text(encoding="utf-8")
        files = extract_files_from_text(text)
        if files:
            return files

    # ถ้าไม่มี ใช้ debugger
    debugger_file = next(
        (f for f in session_path.iterdir() if f.name.endswith("debugger.md")),
        None
    )
    if debugger_file:
        text = debugger_file.read_text(encoding="utf-8")
        files = extract_files_from_text(text)
        if files:
            return files

    # ถ้ายังไม่มี รวม coder + frontend (resolve by phase_id — see
    # _session_phase_files docstring for why hardcoded "04_/05_" is wrong).
    combined = ""
    for f in _session_phase_files(session_path, ["coder", "frontend"]):
        combined += f.read_text(encoding="utf-8") + "\n\n"

    if combined:
        return extract_files_from_text(combined)

    return {}


def build_zip(files: dict) -> bytes:
    """
    สร้าง zip จาก dict {filename: content}
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    buf.seek(0)
    return buf.read()


def build_full_export_zip(session_path: Path, combined_txt: str) -> bytes:
    """
    สร้าง zip ครบ — รวม source files + TXT + meta + raw outputs
    """
    files = extract_from_session(session_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # source code
        for filename, content in files.items():
            zf.writestr(f"code/{filename}", content)
        
        # combined TXT
        zf.writestr("report.txt", combined_txt)
        
        # raw outputs ของแต่ละ phase
        for f in sorted(session_path.iterdir()):
            if not f.is_file():
                continue
            try:
                zf.writestr(f"raw/{f.name}", f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                # ถ้าอ่านเป็นข้อความไม่ได้ ใช้ bytes
                try:
                    zf.writestr(f"raw/{f.name}", f.read_bytes())
                except Exception:
                    pass
    
    buf.seek(0)
    return buf.read()
