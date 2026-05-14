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


CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)\n```", re.DOTALL)

# patterns สำหรับหา filename
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
    """
    หา filename จากบรรทัดต้นๆ ของ code block
    Returns: (filename or None, lines_to_skip)
    """
    lines = code.split("\n")
    # check first 3 lines
    for idx in range(min(3, len(lines))):
        line = lines[idx].strip()
        if not line:
            continue
        for pat in FILENAME_PATTERNS:
            m = pat.match(line)
            if m:
                return m.group(1).strip(), idx + 1
    return None, 0


def extract_files_from_text(text: str) -> dict:
    """
    หา code block ทั้งหมด → คืน {filename: content}
    
    ถ้า block ไหนไม่มี filename → ตั้งชื่อ block_NN.<ext>
    """
    files = {}
    unnamed_counter = 1
    
    for match in CODE_BLOCK_RE.finditer(text):
        lang = match.group(1).lower()
        code = match.group(2)
        
        filename, skip = find_filename_in_block(code)
        actual_code = "\n".join(code.split("\n")[skip:]).strip()
        
        if not actual_code:
            continue
        
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


def extract_from_session(session_path: Path) -> dict:
    """
    ดึงโค้ดจาก session — ลำดับความสำคัญ:
    1. debugger_revision (ล่าสุด) — code หลัง Judge แก้
    2. debugger — code หลัง Debugger ครั้งแรก
    3. coder + frontend — รวมจาก 2 phase
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
    
    # ถ้ายังไม่มี รวม coder + frontend
    combined = ""
    for fname in ["04_coder.md", "05_frontend.md"]:
        f = session_path / fname
        if f.exists():
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
