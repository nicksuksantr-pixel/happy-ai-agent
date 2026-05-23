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
_LOG_MAX_BYTES = 1_000_000   # 1 MB — rotate at this size
_LOG_BACKUP_SUFFIX = ".old"


def _debug_log(msg: str) -> None:
    """Append a timestamped breadcrumb with size-based rotation.

    HPO v1.034 pattern: append-forever logs eventually bloat the user's
    %TEMP% dir. Rotate at 1 MB to a single `.old` backup so the most
    recent breadcrumbs are preserved across at most one rollover.

    Best-effort; never raises.
    """
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with _LOG_LOCK:
            # Cheap size check before opening for append.
            try:
                if _LOG_PATH.exists() and _LOG_PATH.stat().st_size > _LOG_MAX_BYTES:
                    backup = _LOG_PATH.with_suffix(
                        _LOG_PATH.suffix + _LOG_BACKUP_SUFFIX
                    )
                    try:
                        if backup.exists():
                            backup.unlink()
                    except OSError:
                        pass
                    try:
                        _LOG_PATH.rename(backup)
                    except OSError:
                        pass
            except OSError:
                pass
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

_ETAG_PATH = Path.home() / ".happy" / "updater_etag.json"


def _load_etag_cache() -> dict:
    """Return cached {"etag": ..., "data": <release-json>} for the
    /releases/latest endpoint, or {} if missing/corrupt."""
    try:
        if _ETAG_PATH.exists():
            data = json.loads(_ETAG_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _save_etag_cache(etag: str, release_data: dict) -> None:
    """Persist ETag + the release JSON itself. We need the data too
    because a 304 response carries NO body — caller can't re-derive
    download_url/version/size from headers alone. Without the cached
    body we'd be stuck returning None on every 304, which hides the
    available update from clients that are still behind."""
    try:
        _ETAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _ETAG_PATH.write_text(
            json.dumps({"etag": etag, "data": release_data},
                       ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _fetch_latest_release(timeout: float) -> Optional[dict]:
    """Fetch /releases/latest with ETag-conditional GET.

    Sends If-None-Match: <cached-etag>. GitHub returns 304 Not Modified
    when nothing has changed — we return the CACHED release JSON so the
    caller can still run is_newer() against the client's current version.

    **This is the v2.4.1 fix for a critical v2.4.0 bug**: previously we
    treated 304 as "no update available" and returned None. But 304 only
    means "the GitHub resource hasn't changed since you last fetched
    it" — NOT "the client is on the latest version". A v2.3.5 client
    that polled once, got an ETag for the v2.4.0 release, then hit a
    network blip would receive 304 on every subsequent poll for hours
    or days and never be offered the update it actually needs. Caching
    the full release JSON lets the 304 path still run the version
    comparison against fresh client state.

    Bandwidth savings: 304 returns ~200 bytes of headers vs the ~5-10 KB
    JSON body of a 200 response. Rate-limit cost: 304 still counts as 1
    request against the 5000/hr authed quota — same as a 200 — so the
    primary benefit is bandwidth, not quota relief. Kept anyway because
    a kilobyte saved is a kilobyte saved.
    """
    url = f"{GITHUB_API}/repos/{REPO}/releases/latest"
    headers = _auth_headers()
    cache = _load_etag_cache()
    cached_etag = str(cache.get("etag", ""))
    cached_data = cache.get("data") if isinstance(cache.get("data"), dict) else None
    if cached_etag:
        headers["If-None-Match"] = cached_etag
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                _debug_log(f"_fetch_latest_release: HTTP {resp.status}")
                return None
            data = json.loads(resp.read().decode("utf-8"))
            # Cache new ETag + body for next call. Skip the write if
            # ETag is identical to what we already have (shouldn't
            # happen on 200, but defend against weird GitHub behaviour).
            new_etag = resp.headers.get("ETag", "")
            if new_etag and new_etag != cached_etag:
                _save_etag_cache(new_etag, data)
            return data
    except urllib.error.HTTPError as e:
        if e.code == 304:
            # GitHub data hasn't changed since our cached fetch.
            # Return the CACHED body so check_for_update can still
            # compare it against the current client version. If we
            # have no cached data (cache corrupt or first 304 ever
            # somehow), fall through to None — caller treats it as
            # "no update info available right now" and retries in
            # an hour.
            if cached_data:
                _debug_log(
                    "_fetch_latest_release: 304 — returning cached release "
                    f"(tag={cached_data.get('tag_name', '?')})"
                )
                return cached_data
            _debug_log(
                "_fetch_latest_release: 304 but no cached body — treat as None"
            )
            return None
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

def _resume_sidecar_path(dest: Path) -> Path:
    """Sidecar that records WHICH download URL the partial file is for.

    Without this guard the resume path is fundamentally unsafe: if the
    previous attempt was for an OLDER release URL and we now poll a
    NEWER release, the file on disk has bytes from the old asset but
    we'd send `Range: bytes=N-` against the new URL — server returns
    bytes [N..end] of the NEW asset and we append, producing a ZIP
    whose header is from one release and tail from another. The
    extractor then fails with "Bad magic number for central directory"
    and the user sees update install silently fail forever.

    This bug ate v2.3.6 → v2.4.x auto-update on Nick's machine
    (2026-05-23). Pattern adapted from ENA Desktop v2.6.5.
    """
    return dest.with_suffix(dest.suffix + ".meta")


def _validate_partial_for_url(dest: Path, url: str) -> int:
    """If dest exists, decide whether resuming for `url` is safe.

    Returns the byte offset to resume from (0 = start fresh). Side
    effect: if the partial is for a different URL, deletes both the
    partial and its sidecar so the caller falls back to a clean
    full download.
    """
    if not dest.exists():
        return 0
    side = _resume_sidecar_path(dest)
    try:
        if side.exists():
            meta = json.loads(side.read_text(encoding="utf-8"))
            stored_url = str(meta.get("url", ""))
            if stored_url and stored_url == url:
                # Same release URL — safe to resume.
                return dest.stat().st_size
            _debug_log(
                f"  partial download is for a different URL — discarding "
                f"(stored={stored_url[:80]!r}, requested={url[:80]!r})"
            )
        else:
            _debug_log("  partial download has no sidecar — discarding for safety")
    except Exception as e:
        _debug_log(f"  sidecar read failed ({e}) — discarding for safety")
    # Cross-version mismatch or missing sidecar — start clean.
    try:
        dest.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        side.unlink(missing_ok=True)
    except OSError:
        pass
    return 0


def _write_resume_sidecar(dest: Path, url: str) -> None:
    """Mark the partial file as belonging to `url` so a later resume
    can verify the match. Best-effort — failure is non-fatal."""
    try:
        side = _resume_sidecar_path(dest)
        side.write_text(
            json.dumps({"url": url}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _is_valid_zip(path: Path) -> bool:
    """Cheap check: does `path` open as a valid ZIP? Used after a
    download claims success but before we commit to the file — catches
    cross-version Range corruption that the byte-count check misses."""
    try:
        import zipfile
        with zipfile.ZipFile(path) as zf:
            return zf.testzip() is None
    except (zipfile.BadZipFile, OSError, Exception):
        return False


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

    Guards against cross-version Range-resume corruption (v2.4.2 fix):
      • Partial file is paired with a sidecar recording its source URL.
      • Resume only happens when the recorded URL matches the request.
      • Final ZIP is validated; corrupt downloads are wiped + retried
        from scratch.

    Returns (success, message).
    """
    _debug_log(f"download_installer start: url={url} dest={dest}")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _debug_log(f"  dest.mkdir failed: {e}")
        return False, f"Cannot create cache dir: {str(e)[:120]}"

    # Cross-version safety: wipe partial files that belong to a
    # different download URL before we ever send a Range header.
    _validate_partial_for_url(dest, url)
    _write_resume_sidecar(dest, url)

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

            # Byte count is right, but bytes themselves can still be
            # garbage if a previous attempt resumed across a release
            # boundary that the sidecar guard missed. Cheap ZIP magic
            # check catches the remaining cases and forces a clean
            # retry from byte 0.
            if dest.suffix.lower() == ".zip" and not _is_valid_zip(dest):
                _debug_log("  download finished but ZIP is corrupt — wiping for retry")
                try:
                    dest.unlink(missing_ok=True)
                    _resume_sidecar_path(dest).unlink(missing_ok=True)
                except OSError:
                    pass
                last_err = "corrupt zip (bad magic / central directory)"
                continue

            # Final commit — drop the sidecar; partial is now whole.
            try:
                _resume_sidecar_path(dest).unlink(missing_ok=True)
            except OSError:
                pass
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
    """Prune `~/.happy/updates/` to just the active installer.

    Distribution format is now `HappyAIAgent-Setup.zip` (extracted under
    `HappyAIAgent-Setup/` on install). Previous releases shipped `.exe`
    directly. Clean both shapes — keep only the file named `keep` (if
    given) plus its sibling extraction folder. Everything else is gone.

    Called after a successful background download in app.py so the
    cache doesn't accumulate every release forever.
    """
    try:
        d = cache_dir()
        for f in d.iterdir():
            try:
                # Always preserve the file we just downloaded.
                if keep and f.name == keep:
                    continue
                # Preserve its extraction folder too (zip stem).
                if (keep and f.is_dir()
                        and f.name == Path(keep).stem):
                    continue
                if f.is_file() and f.suffix.lower() in (".exe", ".zip"):
                    f.unlink()
                elif f.is_dir():
                    # Old extracted folders from previous installers.
                    import shutil
                    shutil.rmtree(f, ignore_errors=True)
            except Exception:
                pass
    except Exception:
        pass
