"""
builder.py — Build Python code เป็น .exe ด้วย PyInstaller

ใช้ใน HAPPY's page_done — extract code จาก session แล้ว build เป็น .exe
"""
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Tuple, Optional

from extractor import extract_from_session


def _is_test_file(name: str) -> bool:
    """ไฟล์ test (test_*.py / *_test.py / tests.py / conftest.py)
    Fix Bug 6: test files ไม่ควรถูกเลือกเป็น main ของ exe — pytest ใน frozen windowed mode
    จะ crash เพราะ sys.stderr=None (faulthandler.get_stderr_fileno error)"""
    stem = name.lower()
    return (stem.startswith("test_") or stem.endswith("_test.py")
            or stem in ("tests.py", "conftest.py"))


def detect_project_type(files: dict) -> str:
    """ดู extract files แล้วเดาว่า project ประเภทไหน
    Returns: 'python' | 'web' | 'unknown'

    - python: มีไฟล์ .py ที่ไม่ใช่ test → main + (optionally) test files
    - web: มี .html — wrap ด้วย pywebview launcher ตอน build .exe
    - unknown: ไม่มีทั้งคู่
    """
    has_main_py = any(
        name.endswith(".py") and not _is_test_file(name) for name in files
    )
    has_html = any(name.endswith(".html") for name in files)
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
    try:
        subprocess.run(
            [sys.executable, "-c", f"import {pkg_import_name}"],
            check=True, capture_output=True, timeout=10
        )
        return True, "already installed"
    except Exception:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pip_name],
                check=True, capture_output=True, timeout=180, text=True
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
    ok, msg = ensure_pyinstaller_installed()
    if not ok:
        return False, f"PyInstaller ลงไม่ได้: {msg}", None, None

    # สร้าง temp workspace
    with tempfile.TemporaryDirectory(prefix="happy_build_") as tmp:
        tmp_path = Path(tmp)
        # Fix Bug 6: ข้าม test_*.py — pytest ใน frozen exe crash จาก sys.stderr=None
        for name, content in files.items():
            if name.endswith(".py") and not _is_test_file(name):
                (tmp_path / name).write_text(content, encoding="utf-8")

        exe_name = Path(main_file).stem
        _progress(f"🔨 กำลัง build {exe_name}.exe ... (~30-60 วินาที)")

        # Fix Bug 6: ใช้ --console แทน --windowed
        # --windowed สร้าง exe ที่ไม่มี console → sys.stderr=None → ทุก lib ที่ใช้ stderr.fileno()
        # (pytest faulthandler, logging.StreamHandler, etc.) จะ crash
        # --console จะมี console window แต่ปลอดภัยกว่าและ error visible ได้
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--console",
            "--onefile",
            "--noconfirm",
            "--name", exe_name,
            "--distpath", str(tmp_path / "dist"),
            "--workpath", str(tmp_path / "build"),
            "--specpath", str(tmp_path),
            str(tmp_path / main_file),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=300, text=True, cwd=str(tmp_path)
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

_WEB_LAUNCHER_TEMPLATE = '''"""HAPPY-generated launcher — wraps {html_name} with pywebview as native desktop window."""
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
        title = Path(main_html).stem.replace("_", " ").replace("-", " ").title() or "HAPPY App"
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
        cmd = [
            sys.executable, "-m", "PyInstaller",
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
                cmd, capture_output=True, timeout=600, text=True, cwd=str(tmp_path)
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
