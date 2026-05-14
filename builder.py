"""
builder.py — Build Python code เป็น .exe ด้วย PyInstaller

ใช้ใน HAPPY's page_done — extract code จาก session แล้ว build เป็น .exe
"""
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Tuple, Optional

from extractor import extract_from_session


def find_main_python_file(files: dict) -> Optional[str]:
    """หาไฟล์ Python หลัก — preferable: app.py, main.py, หรือไฟล์ .py แรกที่มี if __name__"""
    py_files = [name for name in files if name.endswith(".py")]
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


def ensure_pyinstaller_installed() -> Tuple[bool, str]:
    """ตรวจสอบ + auto-install PyInstaller ถ้ายังไม่มี"""
    try:
        subprocess.run(
            [sys.executable, "-c", "import PyInstaller"],
            check=True, capture_output=True, timeout=10
        )
        return True, "already installed"
    except Exception:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "pyinstaller"],
                check=True, capture_output=True, timeout=180, text=True
            )
            return True, "installed"
        except subprocess.CalledProcessError as e:
            return False, f"install failed: {e.stderr[:200] if e.stderr else str(e)[:200]}"
        except Exception as e:
            return False, f"install error: {str(e)[:200]}"


def build_exe_from_session(session_path: Path, progress_cb=None) -> Tuple[bool, str, Optional[bytes], Optional[str]]:
    """
    Build .exe จาก code ใน session

    Returns: (success, message, exe_bytes_or_None, exe_filename_or_None)
    """
    def _progress(msg):
        if progress_cb:
            progress_cb(msg)

    _progress("🔍 ค้นหาโค้ด Python ใน session...")
    files = extract_from_session(session_path)
    if not files:
        return False, "ไม่เจอ code block ใน session", None, None

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
        # เขียนทุก .py file (สมมติ project มีหลายไฟล์)
        for name, content in files.items():
            if name.endswith(".py"):
                (tmp_path / name).write_text(content, encoding="utf-8")

        exe_name = Path(main_file).stem
        _progress(f"🔨 กำลัง build {exe_name}.exe ... (~30-60 วินาที)")

        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--windowed",
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
