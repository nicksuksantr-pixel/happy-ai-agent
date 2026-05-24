"""
builder.py — Build Python code เป็น .exe ด้วย PyInstaller

ใช้ใน HAPPY's page_done — extract code จาก session แล้ว build เป็น .exe
"""
import os
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Tuple, Optional

from extractor import extract_from_session

# Fix v2.0.4 (Nick directive 2026-05-22): when HAPPY runs as PyInstaller
# --windowed exe, every subprocess we spawn (py.exe / pip / PyInstaller) pops a
# black console window because Windows allocates a new console for any console
# subsystem child when its parent has none. CREATE_NO_WINDOW suppresses that.
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


# Fix P1.3 (2026-05-15 Coddy #4): หา python.exe จริง — ห้ามใช้ sys.executable ใน frozen mode
# Background: ใน HAPPY.exe (PyInstaller frozen), sys.executable = HAPPY.exe ไม่ใช่ python.exe
# → subprocess.run([HAPPY.exe, "-m", "PyInstaller", ...]) พังเงียบๆ หรือเปิด HAPPY.exe ซ้อนเอง
# → Build .exe ปุ่มกดแล้วไม่มีอะไรเกิดขึ้น
_PYTHON_EXE_CACHE: Optional[str] = None


def _looks_like_python(path: str) -> bool:
    """Verify ว่า path เป็น real Python interpreter (ไม่ใช่ HAPPY.exe ที่ rename)"""
    try:
        r = subprocess.run(
            [path, "-c", "import sys; print('PYOK', sys.version_info[0])"],
            capture_output=True, timeout=5, text=True,
            creationflags=_NO_WINDOW,
        )
        return r.returncode == 0 and "PYOK" in (r.stdout or "")
    except Exception:
        return False


def _bundled_python_path() -> Optional[Path]:
    """v2.7.0: locate the embedded Python shipped inside the installer.

    Lives at `_internal/python-embed/python.exe` in the frozen bundle
    (see `installer/build_installer.py` which copies `vendor/python-embed/`
    into the payload). In source mode it's `vendor/python-embed/python.exe`
    relative to the project root — useful for testing the bundled-path
    behaviour without doing a full frozen build.

    Returns the Path if the file exists, else None. Caller still has to
    smoke-test with `_looks_like_python()` because a corrupted or
    partially-extracted bundle is conceivable.
    """
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        cand = Path(mp) / "python-embed" / "python.exe"
        if cand.exists():
            return cand
    src_cand = (
        Path(__file__).resolve().parent / "vendor" / "python-embed" / "python.exe"
    )
    if src_cand.exists():
        return src_cand
    return None


def _find_python_executable() -> Optional[str]:
    """หา python.exe จริงสำหรับ subprocess — ไม่ใช้ sys.executable เมื่ออยู่ใน frozen exe.

    Search order (v2.7.0 — added bundled-first lookup):
    0. **Bundled embedded Python** at `_internal/python-embed/python.exe`
       — shipped inside the installer payload, zero user setup needed
    1. NOT frozen + no bundled → sys.executable
    2. py.exe Windows launcher (handle versions)
    3. PATH lookup (python.exe / python3.exe)
    4. Common install locations

    The bundled lookup runs in BOTH source mode (via `vendor/python-embed/`)
    AND frozen mode (via `sys._MEIPASS/python-embed/`), so the same code
    path works for dev testing + production. This makes "Build .exe" work
    out-of-the-box on a fresh user machine with no Python installed.

    Returns: path to python.exe — หรือ None ถ้าหาไม่เจอ
    """
    global _PYTHON_EXE_CACHE
    if _PYTHON_EXE_CACHE:
        return _PYTHON_EXE_CACHE

    # 0. Bundled embedded Python (v2.7.0) — always preferred.
    bundled = _bundled_python_path()
    if bundled and _looks_like_python(str(bundled)):
        _PYTHON_EXE_CACHE = str(bundled)
        return _PYTHON_EXE_CACHE

    if not getattr(sys, "frozen", False):
        _PYTHON_EXE_CACHE = sys.executable
        return _PYTHON_EXE_CACHE

    # Frozen mode + no bundled python (broken install?) — fall back to
    # external Python search so the user isn't dead in the water.
    candidates: list = []

    # 1. py.exe (Windows Python Launcher) — ปลอดภัยสุด
    py_launcher = shutil.which("py")
    if py_launcher:
        candidates.append(py_launcher)

    # 2. PATH lookup
    for name in ("python.exe", "python3.exe", "python"):
        found = shutil.which(name)
        if found and found not in candidates:
            candidates.append(found)

    # 3. Common Windows install paths
    user_home = Path.home()
    for ver in ("313", "312", "311", "310", "39"):
        candidates.append(str(user_home / "AppData" / "Local" / "Programs" / "Python" / f"Python{ver}" / "python.exe"))
        candidates.append(f"C:/Python{ver}/python.exe")

    # Verify แต่ละ candidate
    for c in candidates:
        if c and Path(c).exists() and _looks_like_python(c):
            _PYTHON_EXE_CACHE = c
            return c

    return None


PYTHON_MISSING_SENTINEL = "__PYTHON_MISSING__"


def _no_python_help_message() -> str:
    """Sentinel returned when Python is missing. The UI catches this and
    offers winget-based install (see `install_python_via_winget`); if the
    user declines or winget fails, the UI opens python.org as a fallback.

    Why a sentinel: build_exe_from_session is called from a worker thread
    that can't surface confirm dialogs. UI flow controls the prompt.
    """
    return PYTHON_MISSING_SENTINEL


def _check_winget_available() -> bool:
    """Return True if winget is installed and on PATH (Windows 11 default).
    Cached behaviour not needed — only called when Python is missing."""
    return shutil.which("winget") is not None


def install_python_via_winget(
    progress_cb=None,
    package_id: str = "Python.Python.3.13",
) -> tuple:
    """Install Python via winget. Returns (success: bool, message: str).

    Designed for the "no Python" recovery path in the .exe builder —
    when the user's machine doesn't have Python yet, this fetches it
    quietly so the next Build .exe attempt succeeds.

    The call is synchronous (winget blocks until install finishes).
    Caller should run in a worker thread + show a progress modal.

    progress_cb(text: str) is called with status text as winget streams.
    Returns immediately with (False, "winget not available") if winget
    isn't on PATH.
    """
    if not _check_winget_available():
        return False, "winget not available — please install Python manually"

    args = [
        "winget", "install", "--id", package_id,
        "--silent", "--accept-package-agreements",
        "--accept-source-agreements",
        # --scope user keeps Windows from prompting UAC for admin install
        "--scope", "user",
    ]
    try:
        if progress_cb:
            try:
                progress_cb("Starting Python installation via winget...")
            except Exception:
                pass
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=_NO_WINDOW,
        )
        # Stream stdout to progress_cb for the user — winget reports
        # progress lines (e.g. "Downloading...", "Installing...").
        for line in iter(proc.stdout.readline, ""):
            line = (line or "").strip()
            if line and progress_cb:
                try:
                    progress_cb(line[:120])
                except Exception:
                    pass
        proc.wait(timeout=300)
        if proc.returncode == 0:
            # Bust the cache so the next _find_python_executable() call
            # re-scans the system.
            global _PYTHON_EXE_CACHE
            _PYTHON_EXE_CACHE = None
            return True, "Python installed successfully via winget"
        return False, (
            f"winget exited with code {proc.returncode} — "
            f"try installing Python manually from python.org"
        )
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        return False, "winget install timed out after 5 minutes"
    except Exception as e:
        return False, f"winget install error: {str(e)[:120]}"


def open_python_org() -> None:
    """Manual fallback: open python.org in the user's browser."""
    try:
        import webbrowser
        webbrowser.open("https://www.python.org/downloads/")
    except Exception:
        pass


def _is_test_file(name: str) -> bool:
    """ไฟล์ test (test_*.py / *_test.py / tests.py / conftest.py / anything under tests/)
    Fix Bug 6: test files ไม่ควรถูกเลือกเป็น main ของ exe — pytest ใน frozen windowed mode
    จะ crash เพราะ sys.stderr=None (faulthandler.get_stderr_fileno error)

    v2.7.1 (Nick caught live): check BASENAME, not the full path. Previous
    impl returned False for `tests/test_logic.py` (path doesn't start with
    "test_", it starts with "tests/") → test file slipped past the filter →
    builder tried to write it under `tmp/tests/test_logic.py` without
    creating the `tests/` subdir → FileNotFoundError.

    Also: anything under a top-level `tests/` directory is considered a
    test file, even if the basename doesn't match — covers e.g.
    `tests/helpers.py` which isn't a test but lives with them.
    """
    # Normalise both slash flavours so "tests/x.py" and "tests\\x.py" hit the same path.
    norm = name.replace("\\", "/")
    parts = norm.split("/")
    if len(parts) > 1 and parts[0].lower() in ("tests", "test"):
        return True
    base = parts[-1].lower()
    return (base.startswith("test_") or base.endswith("_test.py")
            or base in ("tests.py", "conftest.py"))


def detect_project_type(files: dict) -> str:
    """ดู extract files แล้วเดาว่า project ประเภทไหน
    Returns: 'python' | 'web' | 'unknown'

    - python: มีไฟล์ .py ที่ไม่ใช่ test → main + (optionally) test files
    - web: มี .html — wrap ด้วย pywebview launcher ตอน build .exe
    - unknown: ไม่มีทั้งคู่

    Fix Bug 19 (Coddy #5 2026-05-15): ถ้ามีทั้ง .py + .html → prefer "web"
    ถ้า HTML content ใหญ่กว่า Python (AI มักเขียน main.py throwaway สำหรับ web project
    เช่น metadata script ที่ไม่ได้รัน). Heuristic: HTML chars > 2 * py chars และ HTML > 2 KB
    """
    has_main_py = any(
        name.endswith(".py") and not _is_test_file(name) for name in files
    )
    has_html = any(name.endswith(".html") for name in files)

    if has_main_py and has_html:
        html_chars = sum(
            len(files[n]) if isinstance(files[n], str) else 0
            for n in files if n.endswith(".html")
        )
        py_chars = sum(
            len(files[n]) if isinstance(files[n], str) else 0
            for n in files if n.endswith(".py") and not _is_test_file(n)
        )
        # HTML ครองงาน → ถือว่า web project (Python = noise)
        if html_chars > max(py_chars * 2, 2000):
            return "web"

    if has_main_py:
        return "python"
    if has_html:
        return "web"
    return "unknown"


def find_main_html_file(files: dict) -> Optional[str]:
    """หาไฟล์ HTML หลัก — preference: index.html → main.html → first .html"""
    html_files = [name for name in files if name.endswith(".html")]
    if not html_files:
        return None
    for preferred in ("index.html", "main.html"):
        if preferred in html_files:
            return preferred
    return html_files[0]


def find_main_python_file(files: dict) -> Optional[str]:
    """หาไฟล์ Python หลัก — preferable: app.py, main.py, หรือไฟล์ .py แรกที่มี if __name__
    ข้าม test_*.py — test files ไม่ใช่ entry point"""
    py_files = [name for name in files if name.endswith(".py") and not _is_test_file(name)]
    if not py_files:
        return None
    # priority — main / app / __main__
    for preferred in ("main.py", "app.py", "__main__.py"):
        if preferred in py_files:
            return preferred
    # ไฟล์ที่มี if __name__ == "__main__"
    for name in py_files:
        if '__name__' in files[name] and '__main__' in files[name]:
            return name
    return py_files[0]


def _ensure_pkg_installed(pkg_import_name: str, pip_name: Optional[str] = None) -> Tuple[bool, str]:
    """ตรวจสอบ + auto-install package ถ้ายังไม่มี"""
    pip_name = pip_name or pkg_import_name
    py = _find_python_executable()
    if not py:
        return False, _no_python_help_message()
    try:
        subprocess.run(
            [py, "-c", f"import {pkg_import_name}"],
            check=True, capture_output=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
        return True, "already installed"
    except Exception:
        try:
            subprocess.run(
                [py, "-m", "pip", "install", pip_name],
                check=True, capture_output=True, timeout=180, text=True,
                creationflags=_NO_WINDOW,
            )
            return True, "installed"
        except subprocess.CalledProcessError as e:
            return False, f"install failed: {e.stderr[:200] if e.stderr else str(e)[:200]}"
        except Exception as e:
            return False, f"install error: {str(e)[:200]}"


def ensure_pyinstaller_installed() -> Tuple[bool, str]:
    return _ensure_pkg_installed("PyInstaller", "pyinstaller")


def ensure_pywebview_installed() -> Tuple[bool, str]:
    return _ensure_pkg_installed("webview", "pywebview")


# ─── v2.7.1: auto-install user-code dependencies before PyInstaller ─────────
# Without this, every .exe build that imports anything beyond stdlib +
# customtkinter crashes at runtime with `ModuleNotFoundError`. Nick caught
# this live: agent wrote `import speedtest`, build "succeeded", running the
# .exe popped "No module named 'speedtest'".

# Python 3.13 stdlib top-level names — anything not in here is treated as a
# third-party dependency that needs `pip install`. Keep conservative: false
# negatives (calling stdlib a third-party) just cause a no-op pip call.
# Source: `sys.stdlib_module_names` snapshot from CPython 3.13.
_STDLIB_MODULES = frozenset({
    "__future__", "_thread", "abc", "argparse", "array", "ast", "asyncio",
    "atexit", "base64", "bdb", "binascii", "bisect", "builtins", "bz2",
    "calendar", "cmath", "cmd", "code", "codecs", "codeop", "collections",
    "colorsys", "compileall", "concurrent", "configparser", "contextlib",
    "contextvars", "copy", "copyreg", "csv", "ctypes", "curses", "dataclasses",
    "datetime", "dbm", "decimal", "difflib", "dis", "doctest", "email",
    "encodings", "ensurepip", "enum", "errno", "faulthandler", "filecmp",
    "fileinput", "fnmatch", "fractions", "ftplib", "functools", "gc",
    "genericpath", "getopt", "getpass", "gettext", "glob", "graphlib", "gzip",
    "hashlib", "heapq", "hmac", "html", "http", "idlelib", "imaplib", "imp",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json", "keyword",
    "linecache", "locale", "logging", "lzma", "mailbox", "marshal", "math",
    "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt", "multiprocessing",
    "netrc", "nntplib", "nt", "ntpath", "numbers", "opcode", "operator",
    "optparse", "os", "pathlib", "pdb", "pickle", "pickletools", "pipes",
    "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath",
    "pprint", "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr",
    "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib",
    "resource", "rlcompleter", "runpy", "sched", "secrets", "select",
    "selectors", "shelve", "shlex", "shutil", "signal", "site", "smtplib",
    "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "ssl", "stat",
    "statistics", "string", "stringprep", "struct", "subprocess", "sunau",
    "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile",
    "telnetlib", "tempfile", "termios", "test", "textwrap", "threading",
    "time", "timeit", "tkinter", "token", "tokenize", "tomllib", "trace",
    "traceback", "tracemalloc", "tty", "turtle", "turtledemo", "types",
    "typing", "unicodedata", "unittest", "urllib", "uu", "uuid", "venv",
    "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound",
    "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport",
    "zlib", "zoneinfo",
})

# Map import-name → PyPI-name where they differ. Most match (`requests`,
# `numpy`, etc.) so we only enumerate the famous mismatches. Anything not
# in the map gets passed through as-is to pip.
_IMPORT_TO_PYPI = {
    "speedtest": "speedtest-cli",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "OpenSSL": "pyOpenSSL",
    "Crypto": "pycryptodome",
    "google": "google-api-python-client",
    "googleapiclient": "google-api-python-client",
    "genai": "google-genai",
    "discord": "discord.py",
    "telegram": "python-telegram-bot",
    "MySQLdb": "mysqlclient",
    "psycopg2": "psycopg2-binary",
    "wx": "wxPython",
    "serial": "pyserial",
    "usb": "pyusb",
    "win32api": "pywin32",
    "win32com": "pywin32",
    "win32gui": "pywin32",
    "pythoncom": "pywin32",
}

_IMPORT_RE = re.compile(
    r"^[ \t]*(?:from[ \t]+(?P<from>[a-zA-Z_][\w.]*)|import[ \t]+(?P<imp>[a-zA-Z_][\w., ]*))",
    re.MULTILINE,
)


def _scan_imports_for_pip(files: dict) -> list:
    """Walk all `.py` files in the extracted code, return a sorted list of
    PyPI package names that look like third-party dependencies.

    v2.7.1: this is the recovery path for agents that forget `requirements.txt`.
    The directive in `agents.PROJECT_TYPE_DIRECTIVES["desktop_installer"]`
    REQUIRES the Coder to emit `requirements.txt`, but the LLM doesn't
    always comply. Static scanning catches obvious cases (`import speedtest`,
    `import requests`) and triggers a pip install before PyInstaller runs.

    False positives are cheap: pip installs a stdlib-named package only if
    one happens to exist on PyPI, otherwise we get a harmless "not found"
    that we ignore.
    """
    found = set()
    for name, content in files.items():
        if not name.endswith(".py") or not isinstance(content, str):
            continue
        for m in _IMPORT_RE.finditer(content):
            raw = m.group("from") or m.group("imp") or ""
            for part in raw.split(","):
                # Take the top-level package — `import foo.bar.baz` → `foo`.
                pkg = part.strip().split(".")[0].split(" as ")[0].strip()
                if not pkg or pkg.startswith("_"):
                    continue
                if pkg in _STDLIB_MODULES:
                    continue
                found.add(pkg)
    # Local-file imports (the agent's own modules) are also caught by the
    # scan. Filter them out by checking against the extracted file basenames.
    local_module_names = {
        Path(n).stem for n in files
        if n.endswith(".py") and not _is_test_file(n)
    }
    found -= local_module_names
    # Map to PyPI names.
    return sorted({_IMPORT_TO_PYPI.get(p, p) for p in found})


def _install_user_deps(py: str, files: dict, tmp_path: Path, progress_cb) -> Tuple[bool, str]:
    """Install the user code's third-party deps into the build Python so
    PyInstaller can bundle them.

    Strategy (in order):
      1. If `requirements.txt` was extracted → use it as authoritative
      2. Else → static-scan all `.py` files for non-stdlib imports

    Returns (ok, message). On failure we DON'T abort the build — PyInstaller
    might still succeed via fallbacks, and we'd rather ship a half-working
    .exe than fail entirely. The user gets a hint message either way.
    """
    pip_args = None
    if "requirements.txt" in files and isinstance(files["requirements.txt"], str):
        req_path = tmp_path / "requirements.txt"
        req_path.write_text(files["requirements.txt"], encoding="utf-8")
        pip_args = [py, "-m", "pip", "install", "--no-warn-script-location",
                    "-r", str(req_path)]
        progress_cb("📦 Installing from requirements.txt ...")
    else:
        deps = _scan_imports_for_pip(files)
        if not deps:
            return True, "no third-party imports detected"
        pip_args = [py, "-m", "pip", "install", "--no-warn-script-location",
                    *deps]
        progress_cb(f"📦 Auto-installing {len(deps)} dep(s): {', '.join(deps[:6])}{'...' if len(deps) > 6 else ''}")

    try:
        proc = subprocess.run(
            pip_args, capture_output=True, timeout=300, text=True,
            creationflags=_NO_WINDOW,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-400:]
            return False, f"pip install reported errors (build will continue anyway):\n{tail}"
        return True, "ok"
    except subprocess.TimeoutExpired:
        return False, "pip install timed out after 5 min (build will continue)"
    except Exception as e:
        return False, f"pip install error: {str(e)[:200]}"


def build_exe_from_session(session_path: Path, progress_cb=None) -> Tuple[bool, str, Optional[bytes], Optional[str]]:
    """
    Build .exe จาก code ใน session — dispatch ตาม project type:
      - Python project → bundle .py → exe
      - Web (HTML/JS/CSS) → wrap ด้วย pywebview launcher → exe

    Returns: (success, message, exe_bytes_or_None, exe_filename_or_None)
    """
    def _progress(msg):
        if progress_cb:
            progress_cb(msg)

    _progress("🔍 ค้นหาโค้ดใน session...")
    files = extract_from_session(session_path)
    if not files:
        return False, "ไม่เจอ code block ใน session", None, None

    ptype = detect_project_type(files)
    if ptype == "web":
        return _build_web_exe(files, _progress)
    if ptype != "python":
        return False, "ไม่รองรับ — ไม่เจอทั้งไฟล์ .py และ .html ใน output", None, None

    main_file = find_main_python_file(files)
    if not main_file:
        return False, "ไม่เจอไฟล์ Python (.py) ใน session", None, None

    _progress(f"📦 เตรียม PyInstaller...")
    py = _find_python_executable()
    if not py:
        return False, _no_python_help_message(), None, None
    ok, msg = ensure_pyinstaller_installed()
    if not ok:
        return False, f"PyInstaller ลงไม่ได้: {msg}", None, None

    # สร้าง temp workspace
    with tempfile.TemporaryDirectory(prefix="happy_build_") as tmp:
        tmp_path = Path(tmp)
        # Fix Bug 6: ข้าม test_*.py — pytest ใน frozen exe crash จาก sys.stderr=None
        # v2.7.1 (Nick caught live): create parent dirs before write — agents
        # often emit `package/main.py` style nested layouts. Previous code
        # silently FileNotFoundError'd when `package/` didn't exist yet, AND
        # `_is_test_file` was checking full-path so `tests/test_logic.py`
        # slipped past the skip filter and detonated on write.
        for name, content in files.items():
            if not name.endswith(".py") or _is_test_file(name):
                continue
            target = tmp_path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        # v2.7.1: install user-code dependencies BEFORE PyInstaller so it
        # can actually find + bundle them. Without this, `import speedtest`
        # in the agent's output silently passes the build but explodes at
        # runtime with `ModuleNotFoundError`. Failure here is non-fatal —
        # PyInstaller might still produce a .exe via lucky stdlib-only
        # imports — so we log and continue.
        deps_ok, deps_msg = _install_user_deps(py, files, tmp_path, _progress)
        if not deps_ok:
            _progress(f"⚠ {deps_msg}")

        exe_name = Path(main_file).stem
        _progress(f"🔨 กำลัง build {exe_name}.exe ... (~30-60 วินาที)")

        # Fix Bug 16 (2026-05-15 Coddy #4): --windowed + runtime hook redirect stdio
        # ก่อนหน้านี้ Coddy #1 ใช้ --console (Bug 6) กัน sys.stderr=None crash —
        # แต่ console window ดำๆ ขึ้นทุกครั้ง user double-click → UX ห่วย
        # Fix ที่ดีกว่า: --windowed (ไม่มี console) + inject runtime hook ที่ patch
        # sys.stdout/stderr/stdin ก่อน user code รัน → ไม่มี crash + ไม่มี console
        runtime_hook = tmp_path / "_happy_stdio_hook.py"
        # Belt-and-suspenders:
        #   (1) redirect None stdio → NUL (กัน user code crash ใน --windowed mode)
        #   (2) ShowWindow(SW_HIDE) — ซ่อน console window ถ้ามี (กันกรณี --windowed ไม่ apply)
        # Nick's directive 2026-05-15: console ไม่ต้องโชว์ — ทำงานพื้นหลังก็พอ
        runtime_hook.write_text(
            'import sys, os\n'
            '# (1) Redirect None stdio for --windowed mode\n'
            'try:\n'
            '    _nul_w = open(os.devnull, "w")\n'
            '    if sys.stdout is None: sys.stdout = _nul_w\n'
            '    if sys.stderr is None: sys.stderr = _nul_w\n'
            'except Exception: pass\n'
            'try:\n'
            '    if sys.stdin is None: sys.stdin = open(os.devnull, "r")\n'
            'except Exception: pass\n'
            '# (2) Hide console window — defensive fallback if --windowed didnt get applied\n'
            'try:\n'
            '    import ctypes\n'
            '    _hwnd = ctypes.windll.kernel32.GetConsoleWindow()\n'
            '    if _hwnd:\n'
            '        ctypes.windll.user32.ShowWindow(_hwnd, 0)  # SW_HIDE\n'
            '        try:\n'
            '            _nul = open(os.devnull, "w")\n'
            '            sys.stdout = _nul\n'
            '            sys.stderr = _nul\n'
            '        except Exception: pass\n'
            'except Exception: pass\n',
            encoding="utf-8",
        )

        # Fix P1.3: ใช้ py (real python) ไม่ใช่ sys.executable (HAPPY.exe ใน frozen mode)
        cmd = [
            py, "-m", "PyInstaller",
            "--windowed",       # no console window — clean UX for end user
            "--onefile",
            "--noconfirm",
            "--runtime-hook", str(runtime_hook),  # fix None stdio in windowed mode
            "--name", exe_name,
            "--distpath", str(tmp_path / "dist"),
            "--workpath", str(tmp_path / "build"),
            "--specpath", str(tmp_path),
            str(tmp_path / main_file),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=300, text=True, cwd=str(tmp_path),
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            return False, "Build timeout (เกิน 5 นาที)", None, None
        except Exception as e:
            return False, f"Build error: {str(e)[:200]}", None, None

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "")[-500:]
            return False, f"PyInstaller fail:\n{err}", None, None

        exe_path = tmp_path / "dist" / f"{exe_name}.exe"
        if not exe_path.exists():
            return False, f"Build เสร็จแต่ไม่เจอไฟล์ {exe_name}.exe", None, None

        _progress("✅ Build สำเร็จ!")
        exe_bytes = exe_path.read_bytes()
        return True, f"Build สำเร็จ ({len(exe_bytes)//1024} KB)", exe_bytes, f"{exe_name}.exe"


# ─── Web (HTML/JS) → pywebview wrapper exe ─────────────────────────────────

_WEB_LAUNCHER_TEMPLATE = '''"""Happy AI Agent-generated launcher — wraps {html_name} with pywebview as native desktop window."""
import os
import sys
import webview


def _resource_path(rel: str) -> str:
    """Locate bundled file — works in both dev mode and PyInstaller frozen exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def main():
    html_path = _resource_path({html_name_repr})
    if not os.path.exists(html_path):
        sys.stderr.write(f"HTML not found: {{html_path}}\\n")
        sys.exit(1)
    webview.create_window(
        title={title_repr},
        url=html_path,
        width=1024,
        height=768,
        resizable=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
'''


def _build_web_exe(files: dict, progress_cb) -> Tuple[bool, str, Optional[bytes], Optional[str]]:
    """Wrap HTML/JS project ด้วย pywebview launcher → .exe via PyInstaller.

    files: dict ของ {filename: content} ที่ extract มาจาก session
    Returns: same shape as build_exe_from_session
    """
    main_html = find_main_html_file(files)
    if not main_html:
        return False, "ไม่เจอไฟล์ .html ใน output", None, None

    progress_cb(f"📦 เตรียม PyInstaller + pywebview...")
    py = _find_python_executable()
    if not py:
        return False, _no_python_help_message(), None, None
    ok, msg = ensure_pyinstaller_installed()
    if not ok:
        return False, f"PyInstaller ลงไม่ได้: {msg}", None, None
    ok, msg = ensure_pywebview_installed()
    if not ok:
        return False, f"pywebview ลงไม่ได้: {msg}", None, None

    with tempfile.TemporaryDirectory(prefix="happy_webbuild_") as tmp:
        tmp_path = Path(tmp)

        # Write all bundleable web assets (html/css/js/json/img) — skip python files
        bundle_assets = []
        for name, content in files.items():
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext in ("html", "css", "js", "json", "txt", "md", "svg"):
                fpath = tmp_path / name
                fpath.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, str):
                    fpath.write_text(content, encoding="utf-8")
                else:
                    fpath.write_bytes(content)
                bundle_assets.append(name)

        if not bundle_assets:
            return False, "ไม่มี asset ที่ bundle ได้", None, None

        # Write launcher
        title = Path(main_html).stem.replace("_", " ").replace("-", " ").title() or "Happy AI Agent App"
        launcher_code = _WEB_LAUNCHER_TEMPLATE.format(
            html_name=main_html,
            html_name_repr=repr(main_html),
            title_repr=repr(title),
        )
        launcher_path = tmp_path / "launcher.py"
        launcher_path.write_text(launcher_code, encoding="utf-8")

        exe_name = Path(main_html).stem or "happy_app"
        progress_cb(f"🔨 กำลัง build {exe_name}.exe ... (~60-90 วินาที)")

        # PyInstaller cmd — bundle all web assets as data files
        # Fix P1.3: ใช้ py (real python) ไม่ใช่ sys.executable (HAPPY.exe ใน frozen mode)
        cmd = [
            py, "-m", "PyInstaller",
            "--windowed",        # web app = no console (pywebview owns window)
            "--onefile",
            "--noconfirm",
            "--name", exe_name,
            "--distpath", str(tmp_path / "dist"),
            "--workpath", str(tmp_path / "build"),
            "--specpath", str(tmp_path),
        ]
        for asset in bundle_assets:
            # PyInstaller --add-data uses os.pathsep separator (Win=`;`, *nix=`:`)
            cmd.extend(["--add-data", f"{tmp_path / asset}{os.pathsep}."])
        cmd.append(str(launcher_path))

        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=600, text=True, cwd=str(tmp_path),
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            return False, "Web build timeout (เกิน 10 นาที)", None, None
        except Exception as e:
            return False, f"Web build error: {str(e)[:200]}", None, None

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "")[-500:]
            return False, f"PyInstaller fail (web):\n{err}", None, None

        exe_path = tmp_path / "dist" / f"{exe_name}.exe"
        if not exe_path.exists():
            return False, f"Web build เสร็จแต่ไม่เจอ {exe_name}.exe", None, None

        progress_cb("✅ Web Build สำเร็จ!")
        exe_bytes = exe_path.read_bytes()
        return (True,
                f"Web Build สำเร็จ ({len(exe_bytes)//1024} KB) — wrap {main_html} + {len(bundle_assets)} assets",
                exe_bytes, f"{exe_name}.exe")
