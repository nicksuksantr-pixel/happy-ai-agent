"""
updater.py — Check GitHub Releases for newer version, download installer, relaunch

Public API:
  • check_for_update(current_version, timeout=3.0) -> UpdateInfo | None
  • download_installer(url, dest, progress_cb, cancel_event) -> tuple[bool, str]
  • launch_installer_and_exit(installer_path, silent=True)

Repo is configured via env var `HAPPY_AI_UPDATE_REPO` (owner/name) or REPO constant.
Designed to fail silently — never block app startup or crash on network error.

Debug breadcrumbs land in %TEMP%/happy-ai-agent-updater.log — windowed
exes have no stderr, so on-disk logging is the only way to diagnose failures.

Adapted from Happy Photo Organizer's core/updater.py (proven pattern).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# Default — change here or via env var at release time
REPO = os.environ.get("HAPPY_AI_UPDATE_REPO", "nicksuksantr-pixel/happy-ai-agent")
# Distribution is a ZIP (folder-mode installer wrapped) — updater will need to
# extract before running. Asset name matches releases asset.
INSTALLER_ASSET_NAME = "HappyAIAgent-Setup.zip"
GITHUB_API = "https://api.github.com"


def _get_token() -> str:
    """Lazy-read the PAT every call so we pick up .env values that may
    have been loaded AFTER this module was imported. (core.config loads
    .env on import, but app.py imports updater BEFORE core.config — see
    feedback note in v2.3.3 changelog.)"""
    return os.environ.get("HAPPY_AI_UPDATE_TOKEN", "").strip()


# Kept for back-compat reads (Settings page "Check for updates" reads
# this to log "token configured: True/False"). Don't rely on it at
# request time — use _get_token() inside the request path.
UPDATE_TOKEN = _get_token()


def _auth_headers(accept: str = "application/vnd.github+json") -> dict:
    """Headers for all GitHub API requests. Adds Bearer auth if a PAT
    is configured — required for private repo releases."""
    h = {
        "Accept": accept,
        "User-Agent": "HappyAIAgent-Updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _get_token()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

# ─── Debug log (breadcrumbs to %TEMP%) ───
_LOG_PATH = Path(tempfile.gettempdir()) / "happy-ai-agent-updater.log"
_LOG_LOCK = threading.Lock()


def _debug_log(msg: str) -> None:
    """Append a timestamped breadcrumb. Best-effort; never raises."""
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with _LOG_LOCK:
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


@dataclass
class UpdateInfo:
    version: str
    tag: str
    name: str
    body: str
    html_url: str
    download_url: str
    size: int


# ─── Version compare ───

def _parse_version(s: str) -> tuple:
    s = s.strip().lstrip("vV")
    parts = re.split(r"[.\-_+]", s)
    out = []
    for p in parts:
        m = re.match(r"^\d+", p)
        out.append(int(m.group(0)) if m else 0)
    return tuple(out) if out else (0,)


def is_newer(current: str, latest: str) -> bool:
    a = _parse_version(current)
    b = _parse_version(latest)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return b > a


# ─── GitHub Releases API ───

def _fetch_latest_release(timeout: float) -> Optional[dict]:
    url = f"{GITHUB_API}/repos/{REPO}/releases/latest"
    req = urllib.request.Request(url, headers=_auth_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                _debug_log(f"_fetch_latest_release: HTTP {resp.status}")
                return None
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _debug_log(f"_fetch_latest_release: HTTPError {e.code}")
        return None
    except (urllib.error.URLError,
            TimeoutError, OSError, json.JSONDecodeError) as e:
        _debug_log(f"_fetch_latest_release: {type(e).__name__}: {str(e)[:80]}")
        return None


def check_for_update(current_version: str, timeout: float = 3.0) -> Optional[UpdateInfo]:
    """Returns UpdateInfo if a newer release exists, else None.
    Fails silently on any error.
    """
    data = _fetch_latest_release(timeout)
    if not data:
        return None
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return None
    latest_ver = tag.lstrip("vV")
    if not is_newer(current_version, latest_ver):
        return None

    assets = data.get("assets") or []
    asset = None
    for a in assets:
        if a.get("name") == INSTALLER_ASSET_NAME:
            asset = a
            break
    if not asset:
        for a in assets:
            if str(a.get("name", "")).lower().endswith(".exe"):
                asset = a
                break
    if not asset:
        return None

    # For PRIVATE repos: download via the asset's API URL (`asset.url`)
    # because `browser_download_url` 302s to S3 which strips the auth
    # header. For PUBLIC repos either works — we use browser_download_url
    # as the fallback when no token is set.
    if _get_token() and asset.get("url"):
        download_url = str(asset.get("url"))
    else:
        download_url = str(asset.get("browser_download_url") or "")

    return UpdateInfo(
        version=latest_ver,
        tag=tag,
        name=str(data.get("name") or tag),
        body=str(data.get("body") or "").strip(),
        html_url=str(data.get("html_url") or ""),
        download_url=download_url,
        size=int(asset.get("size") or 0),
    )


# ─── Download ───

def download_installer(
    url: str,
    dest: Path,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    chunk_size: int = 64 * 1024,
    max_attempts: int = 3,
    attempt_timeout: float = 300.0,
) -> tuple:
    """Download URL → dest with retry + HTTP Range resume.
    Returns (success, message).
    """
    _debug_log(f"download_installer start: url={url} dest={dest}")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _debug_log(f"  dest.mkdir failed: {e}")
        return False, f"Cannot create cache dir: {str(e)[:120]}"

    expected_total = 0
    last_err = "unknown"

    for attempt in range(1, max_attempts + 1):
        resume_from = dest.stat().st_size if dest.exists() else 0
        if expected_total > 0 and resume_from >= expected_total:
            return True, f"Already downloaded {resume_from:,} bytes"

        # `application/octet-stream` is required when using the asset's
        # API URL for private-repo downloads — without it GitHub returns
        # metadata JSON instead of the binary.
        headers = _auth_headers(accept="application/octet-stream")
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=attempt_timeout) as resp:
                status = resp.status
                cl = int(resp.headers.get("Content-Length") or 0)
                cr = resp.headers.get("Content-Range") or ""
                if cr:
                    m = re.search(r"/(\d+)$", cr)
                    if m:
                        expected_total = int(m.group(1))
                elif cl and resume_from == 0:
                    expected_total = cl
                _debug_log(f"  attempt {attempt}: HTTP {status} expected_total={expected_total}")

                file_mode = "ab" if status == 206 and resume_from > 0 else "wb"
                if file_mode == "wb":
                    resume_from = 0

                done = resume_from
                with open(dest, file_mode) as f:
                    while True:
                        if cancel_event and cancel_event.is_set():
                            try:
                                f.close()
                                dest.unlink(missing_ok=True)
                            except Exception:
                                pass
                            return False, "Cancelled"
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if progress_cb:
                            try:
                                progress_cb(done, expected_total or done)
                            except Exception:
                                pass

            actual_size = dest.stat().st_size if dest.exists() else 0
            if expected_total > 0 and actual_size < expected_total:
                last_err = f"truncated: {actual_size:,}/{expected_total:,} bytes"
                continue

            _debug_log(f"  SUCCESS — {actual_size:,} bytes")
            return True, f"Downloaded {actual_size:,} bytes"

        except (urllib.error.URLError, urllib.error.HTTPError,
                 TimeoutError, OSError) as e:
            last_err = f"{type(e).__name__}: {str(e)[:140]}"
            _debug_log(f"  attempt {attempt} failed: {last_err}")
            if attempt < max_attempts:
                time.sleep(min(2 ** (attempt - 1), 8))

    try:
        dest.unlink(missing_ok=True)
    except Exception:
        pass
    _debug_log(f"download_installer FAILED: {last_err}")
    return False, f"Download failed after {max_attempts} attempts: {last_err}"


# ─── Launch installer + exit ───

def launch_installer_and_exit(installer_path: Path, silent: bool = True) -> None:
    """Spawn installer (detached) then exit current process.

    `installer_path` may be either a `.zip` (the released distribution
    format — contains `HappyAIAgent-Setup/HappyAIAgent-Setup.exe`) or a
    `.exe` directly. For zips we extract to a temp folder first.

    Silent mode passes `--silent --upgrade` so the installer skips its UI.
    """
    exe_path = _resolve_installer_exe(installer_path)
    if exe_path is None:
        _debug_log(f"launch_installer_and_exit: could not resolve exe from {installer_path}")
        return  # leave the app running; the user can try again

    args = [str(exe_path)]
    if silent:
        args.extend(["--silent", "--upgrade"])
    _debug_log(f"launch_installer_and_exit: spawning {args}")

    try:
        creationflags = 0
        if sys.platform == "win32":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            creationflags = 0x00000008 | 0x00000200
        subprocess.Popen(
            args, creationflags=creationflags, close_fds=True,
            stdin=None, stdout=None, stderr=None,
        )
    except Exception:
        try:
            if sys.platform == "win32":
                os.startfile(str(exe_path))  # type: ignore[attr-defined]
        except Exception:
            pass
    sys.exit(0)


def _resolve_installer_exe(path: Path) -> Optional[Path]:
    """Resolve `path` to a runnable installer .exe.

    - If `path` ends with .exe → return as-is (existence checked).
    - If `path` ends with .zip → extract under cache_dir()/<stem>/ and
      return the first `*-Setup.exe` (or any .exe) found inside.
    - Otherwise return None.
    """
    if not path.exists():
        return None
    if path.suffix.lower() == ".exe":
        return path
    if path.suffix.lower() != ".zip":
        return None

    import zipfile
    extract_dir = cache_dir() / path.stem
    try:
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(extract_dir)
    except Exception as e:
        _debug_log(f"_resolve_installer_exe: unzip failed: {e}")
        return None

    # Find HappyAIAgent-Setup.exe (preferred) or any *.exe inside.
    preferred = None
    fallback = None
    for p in extract_dir.rglob("*.exe"):
        if "setup" in p.name.lower():
            preferred = p
            break
        if fallback is None:
            fallback = p
    return preferred or fallback


# ─── Cache dir helpers ───

def cache_dir() -> Path:
    p = Path.home() / ".happy" / "updates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cleanup_old_installers(keep: Optional[str] = None) -> None:
    """Remove cached installer .exe files, except `keep` filename."""
    try:
        for f in cache_dir().iterdir():
            if f.is_file() and f.suffix.lower() == ".exe":
                if keep and f.name == keep:
                    continue
                try:
                    f.unlink()
                except Exception:
                    pass
    except Exception:
        pass
