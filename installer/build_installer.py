"""
build_installer.py — Build pipeline for HappyAIAgent-Setup distribution

Steps:
  1. Zip dist/HappyAIAgent/ → dist/HappyAIAgent.zip  (payload bundled in installer)
  2. PyInstaller installer.py (folder mode) → dist/HappyAIAgent-Setup/
  3. Pack the installer folder → dist/HappyAIAgent-Setup.zip  (distribution)

Run from project root:
  python installer/build_installer.py

Prereqs:
  pyinstaller HappyAIAgent.spec --noconfirm   # main app must be built first

Why folder mode (not onefile):
  PyInstaller --onefile + --windowed has a known Tk window-creation bug on
  Windows — the Tk window never gets a Win32 HWND so the installer runs
  invisibly. Folder mode is reliable. We wrap the folder in a ZIP for
  one-file distribution.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
APP_DIST = ROOT / "dist" / "HappyAIAgent"
PAYLOAD_ZIP = ROOT / "dist" / "HappyAIAgent.zip"
SETUP_FOLDER = ROOT / "dist" / "HappyAIAgent-Setup"
SETUP_ZIP = ROOT / "dist" / "HappyAIAgent-Setup.zip"
SETUP_EXE = SETUP_FOLDER / "HappyAIAgent-Setup.exe"
INSTALLER_SPEC = ROOT / "installer" / "HappyAIAgentSetup.spec"
# v2.7.0: bundled embedded Python + PyInstaller so the end user can build
# .exe without ever installing Python. Staged via tools/stage_embedded_python.py.
EMBED_SRC = ROOT / "vendor" / "python-embed"
EMBED_DEST_REL = Path("_internal") / "python-embed"


def ensure_embedded_python() -> None:
    """Copy vendor/python-embed/ → dist/HappyAIAgent/_internal/python-embed/.

    v2.7.0 (Nick directive): the .exe builder spawns Python to run
    PyInstaller. If the user has no Python installed, build fails. We
    ship a working Python + PyInstaller inside the installer so it
    works on a clean machine zero-config.

    If vendor/python-embed/ is missing, instruct the developer to run
    the one-time staging script — DON'T silently ship without it (that
    would regress the user experience back to "install Python first").
    """
    if not EMBED_SRC.exists():
        print(f"[!] vendor/python-embed/ not staged.")
        print(f"    Run once: python tools/stage_embedded_python.py")
        sys.exit(1)
    if not APP_DIST.exists():
        # Caller will check this in zip_payload too, but we need APP_DIST
        # to copy into. Fail early with a clearer message.
        print(f"[!] Main app not built at {APP_DIST}")
        print("    Run: pyinstaller HappyAIAgent.spec --noconfirm")
        sys.exit(1)

    dest = APP_DIST / EMBED_DEST_REL
    if dest.exists():
        # Idempotent rebuild: clear stale embed (a re-stage may have changed
        # python patch version or PyInstaller version).
        shutil.rmtree(dest, ignore_errors=True)
    print(f"[*] Copying embedded Python  ->  {dest.relative_to(ROOT)}")
    shutil.copytree(EMBED_SRC, dest)
    total = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    print(f"    Embedded toolchain: {total / (1024 * 1024):.1f} MB")


def zip_payload() -> None:
    if not APP_DIST.exists():
        print(f"[!] Main app not built at {APP_DIST}")
        print("    Run: pyinstaller HappyAIAgent.spec --noconfirm")
        sys.exit(1)

    if PAYLOAD_ZIP.exists():
        PAYLOAD_ZIP.unlink()

    print(f"[*] Zipping {APP_DIST}  ->  {PAYLOAD_ZIP}")
    # arcname relative to APP_DIST itself (not its parent) so files extract
    # directly into install_dir without an extra HappyAIAgent/ nesting level.
    with zipfile.ZipFile(PAYLOAD_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in APP_DIST.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(APP_DIST)
                zf.write(path, arcname)
    size_mb = PAYLOAD_ZIP.stat().st_size / (1024 * 1024)
    print(f"    Payload size: {size_mb:.1f} MB")


def build_installer() -> None:
    print(f"[*] Building installer with {INSTALLER_SPEC.name}")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller",
         str(INSTALLER_SPEC), "--noconfirm", "--clean"],
        cwd=str(ROOT),
        capture_output=True, text=True,
    )
    print(result.stdout[-2000:])
    if result.returncode != 0:
        print(result.stderr[-2000:])
        sys.exit(result.returncode)
    print("[*] Installer folder built at dist/HappyAIAgent-Setup/")


def pack_setup_folder() -> None:
    """Wrap folder-mode installer into a single ZIP for distribution.

    End user extracts the zip and runs HappyAIAgent-Setup/HappyAIAgent-Setup.exe.
    """
    if not SETUP_FOLDER.exists():
        print(f"[!] folder mode output missing at {SETUP_FOLDER}")
        sys.exit(1)
    if SETUP_ZIP.exists():
        SETUP_ZIP.unlink()
    print(f"[*] Packing {SETUP_FOLDER}  ->  {SETUP_ZIP}")
    with zipfile.ZipFile(SETUP_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in SETUP_FOLDER.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(SETUP_FOLDER.parent)
                zf.write(path, arcname)
    size_mb = SETUP_ZIP.stat().st_size / (1024 * 1024)
    print(f"    Setup zip: {size_mb:.1f} MB")


def main() -> int:
    ensure_embedded_python()  # v2.7.0 — must run BEFORE zip_payload
    zip_payload()
    build_installer()
    pack_setup_folder()
    if SETUP_ZIP.exists() and SETUP_EXE.exists():
        sz = SETUP_ZIP.stat().st_size / (1024 * 1024)
        print(f"\n[OK] DONE")
        print(f"  Folder:  dist/HappyAIAgent-Setup/ (run HappyAIAgent-Setup.exe inside)")
        print(f"  Zip:     dist/HappyAIAgent-Setup.zip ({sz:.1f} MB) for distribution")
    else:
        print("\n[!] missing output")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
