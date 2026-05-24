"""One-time setup: stage Python + PyInstaller in vendor/python-embed/.

Why this script exists
----------------------
HAPPY's `builder.py` spawns a real Python interpreter to run PyInstaller
when the user clicks "Build .exe" on a generated project. If the user's
machine has no Python installed, that build fails.

v2.7.0 first tried the python.org **embeddable** distribution. It's
small (12 MB zip) but it OMITS tkinter — and most agent-generated
code uses CustomTkinter / Tkinter for the GUI.

v2.7.2 (Nick caught live ModuleNotFoundError: tkinter on his built .exe):
the embeddable distribution's `python313.dll` is stripped of symbols
that `_tkinter.pyd` needs, so the textbook "copy tkinter from a full
Python install" workaround fails with
`ImportError: DLL load failed while importing _tkinter: The specified
procedure could not be found.`

Replacing the embedded `python313.dll` with the host's full version
then breaks PyInstaller (the embedded distribution is configured
differently in subtle startup paths).

Resolution: **clone the host's full Python install directly**. This
gives us a Python that already has tkinter, Tcl/Tk DLLs, pip,
matched DLLs, the lot. We then layer PyInstaller on top via the
cloned pip. Cost: ~110 MB unpacked vs embedded's ~50 MB — but the
cloned install is the ONLY config we can verify works end-to-end
because it's literally the same one dev tests with.

What this script does
---------------------
1. Mirror the host's `sys.base_prefix` (the real Python install, NOT a
   venv) into `vendor/python-embed/`, skipping the obvious bloat:
   __pycache__, test suites, demo / idle / tutorial modules.
2. Install `pyinstaller` via the cloned `python.exe -m pip install`.
3. Verify: `vendor/python-embed/python.exe -c "import tkinter, PyInstaller"`
   actually works.

The resulting `vendor/python-embed/` is bundled by
`installer/build_installer.py` into `_internal/python-embed/` so HAPPY
finds it via `builder._find_python_executable()` ahead of any system
Python — making the bundled toolchain the default.

Run from project root:
    python tools/stage_embedded_python.py

Idempotent: re-running detects an existing complete install and skips.
Use `--force` to wipe and re-stage from scratch.

Reproducibility caveat: this clones the dev box's Python. CI / other
dev machines must therefore have an equivalent Python 3.13 installed
first. Future v2.8.0 plan: switch to `python-build-standalone` for a
self-contained download path (https://github.com/astral-sh/python-build-standalone).
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

# v2.7.2: switched from python.org embeddable (no tkinter, fragile to
# patch) to Astral's python-build-standalone — a self-contained
# distribution designed exactly for our "embed into a desktop app" case.
# Includes tkinter + Tcl/Tk DLLs + pip + the full stdlib out of the box.
#
# Pin to a specific PBS build for reproducibility. ~30 MB compressed,
# ~115 MB unpacked after stdlib + tkinter + pip but no PyInstaller yet.
PBS_TAG = "20241016"
PYTHON_VERSION = "3.13.0"
PBS_URL = (
    f"https://github.com/astral-sh/python-build-standalone/releases/download/"
    f"{PBS_TAG}/cpython-{PYTHON_VERSION}+{PBS_TAG}-"
    f"x86_64-pc-windows-msvc-shared-install_only_stripped.tar.gz"
)


def _download(url: str, dest: Path) -> None:
    print(f"[*] downloading {url}")
    print(f"        -> {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"        ({size_mb:.1f} MB)")


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


def _verify_tkinter(python_exe: Path) -> None:
    """v2.7.2: confirm `import tkinter` works AND a Tk window can be
    initialised. Just `import tkinter` is necessary-but-not-sufficient —
    if the Tcl scripts dir is misplaced, the import succeeds but
    `tkinter.Tk()` fails with `Can't find a usable init.tcl`.
    """
    print("[*] verifying tkinter")
    res = subprocess.run(
        [str(python_exe), "-c",
         "import tkinter; "
         "r = tkinter.Tk(); r.withdraw(); r.destroy(); "
         "print('OK tkinter Tk init succeeded')"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(res.stdout[-2000:])
        print(res.stderr[-2000:])
        raise RuntimeError("tkinter verification failed")
    print(f"        {res.stdout.strip()}")


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


def _download_pbs_python(embed_dir: Path) -> None:
    """v2.7.2: fetch + extract Astral's python-build-standalone (PBS)
    Windows release into `embed_dir`.

    PBS layout in the tarball:
        python/
        └── install/
            ├── python.exe
            ├── python313.dll
            ├── DLLs/
            ├── Lib/        (full stdlib INCLUDING tkinter)
            ├── tcl/        (Tcl/Tk scripts)
            ├── Scripts/    (pip, etc.)
            └── ...

    We want the contents of `python/install/` to live flat at
    `vendor/python-embed/` so `_find_python_executable()` can use
    `python.exe` at the top.

    Why PBS (vs python.org embeddable or full installer):
      - SMALL: ~30 MB compressed, ~115 MB unpacked
      - SELF-CONTAINED: tkinter + Tcl/Tk + pip out of the box
      - NO HOST COUPLING: download is identical on every dev box
      - DESIGNED for embedding (used by uv, ruff, pyodide, ...)
    """
    embed_dir.mkdir(parents=True, exist_ok=True)
    archive = VENDOR_DIR / f"cpython-{PYTHON_VERSION}-{PBS_TAG}-pbs.tar.gz"
    if not archive.exists():
        _download(PBS_URL, archive)
    else:
        print(f"[*] re-using cached {archive.name}")

    import tarfile

    print(f"[*] extracting PBS tarball -> {embed_dir}")
    # PBS install_only_stripped tar prefix is `python/...` (NOT
    # `python/install/...` like the full install variant). Strip the
    # one leading component so files land directly in embed_dir.
    with tarfile.open(archive, "r:gz") as tf:
        members = []
        for m in tf.getmembers():
            parts = m.name.split("/")
            if len(parts) < 2 or parts[0] != "python":
                continue
            # Re-anchor: drop the "python/" prefix.
            m.name = "/".join(parts[1:])
            if not m.name:
                continue
            members.append(m)
        tf.extractall(embed_dir, members=members, filter="data")

    if not (embed_dir / "python.exe").exists():
        raise RuntimeError(
            f"PBS extract finished but python.exe not at {embed_dir} — "
            f"PBS tarball layout may have changed; check {PBS_URL}"
        )
    total = sum(p.stat().st_size for p in embed_dir.rglob("*") if p.is_file())
    print(f"[*] PBS staged: {total / (1024 * 1024):.1f} MB")


def stage(force: bool = False) -> int:
    python_exe = EMBED_DIR / "python.exe"

    if force and EMBED_DIR.exists():
        print(f"[*] --force: removing {EMBED_DIR}")
        shutil.rmtree(EMBED_DIR, ignore_errors=True)

    # Idempotency: skip if everything works.
    if python_exe.exists():
        try:
            _verify(python_exe)
            _verify_tkinter(python_exe)
            print("[OK] embedded toolchain already staged — nothing to do.")
            print("     use --force to rebuild from scratch.")
            return 0
        except Exception as e:
            print(f"[!] existing embed is broken ({e}), re-staging")
            shutil.rmtree(EMBED_DIR, ignore_errors=True)

    # 1. Download + extract python-build-standalone (tkinter + pip included).
    _download_pbs_python(EMBED_DIR)

    # 2. Install PyInstaller on top using PBS-bundled pip.
    _install_pyinstaller(python_exe)

    # 3. Verify everything
    _verify(python_exe)
    _verify_tkinter(python_exe)

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
