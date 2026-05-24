"""One-time setup: stage embeddable Python + PyInstaller in vendor/python-embed/.

Why this script exists
----------------------
HAPPY's `builder.py` spawns a real Python interpreter to run PyInstaller
when the user clicks "Build .exe" on a generated project. If the user's
machine has no Python installed, that build fails — and the previous
recovery path (winget Python install) requires admin, internet, and
~5 minutes of waiting.

v2.7.0 ships Python + PyInstaller INSIDE the installer payload. The user
can build .exe immediately, offline, with no separate Python install.

What this script does
---------------------
1. Downloads python-3.13.X-embed-amd64.zip from python.org (~12 MB)
2. Extracts to vendor/python-embed/
3. Patches `python313._pth` to enable `site` packages (embedded ships
   with it commented out — required for pip + PyInstaller to work).
4. Downloads `get-pip.py` and runs it against the embedded interpreter.
5. Installs `pyinstaller` (~80 MB unpacked with deps).
6. Verifies: `python-embed/python.exe -m PyInstaller --version` succeeds.

The resulting `vendor/python-embed/` directory is bundled by
`installer/build_installer.py` into `_internal/python-embed/` so HAPPY
finds it via `builder._find_python_executable()` ahead of any system
Python — making the bundled toolchain the default.

Run from project root:
    python tools/stage_embedded_python.py

Idempotent: re-running detects an existing complete install and skips.
Use `--force` to wipe and re-stage from scratch.

Network requirement: downloads from python.org + pypi.org. About
~140 MB of installs once expanded (~25-30 MB compressed into the
shipped installer zip).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = ROOT / "vendor"
EMBED_DIR = VENDOR_DIR / "python-embed"

# Pin to a specific Python patch version so reproducible across machines.
# 3.13.0 is the first stable 3.13 release; bump when a security patch
# lands that we want to ship.
PYTHON_VERSION = "3.13.0"
EMBED_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
    f"python-{PYTHON_VERSION}-embed-amd64.zip"
)
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# The minor-version digits matter for the ._pth file name.
PTH_FILENAME = "python313._pth"


def _download(url: str, dest: Path) -> None:
    print(f"[*] downloading {url}")
    print(f"        -> {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"        ({size_mb:.1f} MB)")


def _enable_site_packages(embed_dir: Path) -> None:
    """The embedded distribution ships with `import site` commented out
    in `pythonNNN._pth` so it runs in "isolated" mode. We need full site
    behaviour so pip and PyInstaller can find their installed packages.
    """
    pth_path = embed_dir / PTH_FILENAME
    if not pth_path.exists():
        # Look for any pythonNN._pth — the version filename varies.
        candidates = list(embed_dir.glob("python*._pth"))
        if not candidates:
            raise FileNotFoundError(
                f"no python*._pth file under {embed_dir} — embedded zip layout changed?"
            )
        pth_path = candidates[0]
    lines = pth_path.read_text(encoding="utf-8").splitlines()
    out = []
    site_uncommented = False
    for line in lines:
        # Uncomment `#import site` so site-packages discovery works.
        stripped = line.lstrip()
        if stripped == "#import site":
            out.append("import site")
            site_uncommented = True
        else:
            out.append(line)
    if not site_uncommented:
        # Already enabled (re-run), append if missing.
        if "import site" not in "\n".join(out):
            out.append("import site")
            site_uncommented = True
    pth_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[*] enabled site-packages in {pth_path.name}")


def _bootstrap_pip(python_exe: Path) -> None:
    print("[*] bootstrapping pip via get-pip.py")
    get_pip = EMBED_DIR / "get-pip.py"
    _download(GET_PIP_URL, get_pip)
    res = subprocess.run(
        [str(python_exe), str(get_pip), "--no-warn-script-location"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(res.stdout[-2000:])
        print(res.stderr[-2000:])
        raise RuntimeError("get-pip.py failed")
    print("[*] pip installed")
    # get-pip.py is no longer needed in the shipped tree.
    try:
        get_pip.unlink()
    except OSError:
        pass


def _install_pyinstaller(python_exe: Path) -> None:
    print("[*] installing PyInstaller into embedded Python")
    res = subprocess.run(
        [str(python_exe), "-m", "pip", "install",
         "--no-warn-script-location", "pyinstaller"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(res.stdout[-2000:])
        print(res.stderr[-2000:])
        raise RuntimeError("pyinstaller install failed")
    print("[*] PyInstaller installed")


def _verify(python_exe: Path) -> None:
    print("[*] verifying embedded toolchain")
    res = subprocess.run(
        [str(python_exe), "-c",
         "import sys, PyInstaller; "
         "print(f'OK python={sys.version_info[:3]} pyinstaller={PyInstaller.__version__}')"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(res.stderr[-2000:])
        raise RuntimeError("verification failed")
    print(f"        {res.stdout.strip()}")


def stage(force: bool = False) -> int:
    python_exe = EMBED_DIR / "python.exe"

    if force and EMBED_DIR.exists():
        print(f"[*] --force: removing {EMBED_DIR}")
        shutil.rmtree(EMBED_DIR, ignore_errors=True)

    # Idempotency: skip download if PyInstaller already importable.
    if python_exe.exists():
        try:
            _verify(python_exe)
            print("[OK] embedded toolchain already staged — nothing to do.")
            print("     use --force to rebuild from scratch.")
            return 0
        except Exception:
            print("[!] existing embed is broken, re-staging")
            shutil.rmtree(EMBED_DIR, ignore_errors=True)

    # 1. Download embedded zip
    EMBED_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = VENDOR_DIR / f"python-{PYTHON_VERSION}-embed-amd64.zip"
    if not zip_path.exists():
        _download(EMBED_URL, zip_path)
    else:
        print(f"[*] re-using cached {zip_path.name}")

    # 2. Extract
    print(f"[*] extracting to {EMBED_DIR}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(EMBED_DIR)

    # 3. Enable site-packages
    _enable_site_packages(EMBED_DIR)

    # 4. Bootstrap pip
    _bootstrap_pip(python_exe)

    # 5. Install PyInstaller
    _install_pyinstaller(python_exe)

    # 6. Verify
    _verify(python_exe)

    # 7. Footprint summary
    total = sum(p.stat().st_size for p in EMBED_DIR.rglob("*") if p.is_file())
    print(f"\n[OK] embedded toolchain ready at {EMBED_DIR}")
    print(f"     footprint: {total / (1024 * 1024):.1f} MB unpacked")
    print(f"     this will be bundled into HappyAIAgent-Setup.zip")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Stage embedded Python + PyInstaller for HAPPY installer."
    )
    ap.add_argument(
        "--force", action="store_true",
        help="wipe vendor/python-embed/ and re-stage from scratch",
    )
    args = ap.parse_args()
    return stage(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
