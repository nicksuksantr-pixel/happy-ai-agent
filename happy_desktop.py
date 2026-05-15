"""
happy_desktop.py — HAPPY Desktop Launcher

Wraps the Streamlit app in a native window using pywebview.
- Starts Streamlit on localhost:8501 in a background thread
- Waits for the server to be ready
- Opens a pywebview window loading the app

Run: python happy_desktop.py
Build .exe: pyinstaller happy_desktop.spec
"""
import os
import sys
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path


HERE = Path(__file__).resolve().parent
APP_FILE = HERE / "app.py"
ICON_FILE = HERE / "assets" / "happy_logo.ico"
PORT = 8501
WINDOW_TITLE = "HAPPY — AI Agent"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_streamlit(timeout: int = 60) -> bool:
    """Poll port 8501 until accepting TCP connections (socket-level, fast)"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                # Got a TCP connection → Streamlit listening
                # Give it a moment to fully initialize before opening window
                time.sleep(1.5)
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.4)
    return False


def _is_frozen() -> bool:
    """True ถ้ารันจาก PyInstaller .exe"""
    return getattr(sys, "frozen", False)


def start_streamlit_embedded() -> None:
    """Start Streamlit ใน thread (ต้อง patch signal handler ก่อน)"""
    # Critical: บังคับ production mode ก่อน import streamlit
    # global.developmentMode=True → Streamlit ไม่ register static asset routes → 404 ทุก path
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    # ซ่อน Streamlit's toolbar (Deploy button + hamburger menu)
    os.environ["STREAMLIT_CLIENT_TOOLBAR_MODE"] = "viewer"
    os.environ["STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION"] = "false"

    # Debug + Fix: PyInstaller frozen mode — Streamlit's file_util.get_static_dir()
    # ใช้ __file__ relative ของ streamlit module — บางครั้งใน frozen ชี้ผิด
    # → patch ให้ใช้ absolute path ของ _internal/streamlit/static
    if _is_frozen():
        # Critical bug fix: Streamlit's _global_development_mode() auto-detects
        # "dev mode" by checking if __file__ contains 'site-packages'.
        # In PyInstaller-frozen mode, __file__ is in _internal/streamlit/ —
        # NOT site-packages — so it returns True. When dev mode is True,
        # Streamlit skips registering static asset routes → ALL paths return 404.
        from streamlit import config as st_config
        try:
            st_config.set_option("global.developmentMode", False,
                                 where_defined="<programmatic frozen-mode override>")
            # บังคับ headless mode → ไม่เปิด browser tab อัตโนมัติ
            # (pywebview จะเปิด native window แทน)
            st_config.set_option("server.headless", True,
                                 where_defined="<programmatic frozen-mode override>")
            print("[HAPPY] Forced developmentMode=False + server.headless=True")
        except Exception as e:
            print(f"[HAPPY] Could not override config: {e}")

    # Also block browser-opening as defense-in-depth (override Streamlit's helper)
    try:
        from streamlit import cli_util
        cli_util.open_browser = lambda *a, **k: None
    except Exception:
        pass

    sys.argv = [
        "streamlit", "run", str(APP_FILE),
        f"--server.port={PORT}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]
    # Patch: Streamlit's bootstrap ใช้ signal.signal ที่ทำงานเฉพาะ main thread
    # ในโหมด embedded เรารัน Streamlit ใน background thread → ต้อง bypass
    from streamlit.web import bootstrap
    bootstrap._set_up_signal_handler = lambda *args, **kwargs: None
    bootstrap.run(str(APP_FILE), False, [], {})


def start_streamlit_subprocess() -> subprocess.Popen:
    """Dev-mode: start Streamlit as subprocess (faster iteration, easier debug)"""
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_HEADLESS"] = "true"

    cmd = [
        sys.executable, "-m", "streamlit", "run", str(APP_FILE),
        f"--server.port={PORT}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(
        cmd, env=env, cwd=str(HERE),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


class _JSApi:
    """JS bridge — รับ blob data จาก browser → save ลง Downloads folder ของ user"""

    def save_download(self, base64_data: str, filename: str):
        """รับไฟล์จาก JS (base64) → save ลง ~/Downloads + return path"""
        try:
            import base64
            from pathlib import Path

            downloads = Path.home() / "Downloads"
            downloads.mkdir(exist_ok=True)

            # Sanitize filename + handle duplicates
            safe_name = Path(filename or "happy_download.bin").name
            target = downloads / safe_name
            counter = 1
            while target.exists():
                stem = Path(safe_name).stem
                suffix = Path(safe_name).suffix
                target = downloads / f"{stem} ({counter}){suffix}"
                counter += 1

            data = base64.b64decode(base64_data)
            target.write_bytes(data)
            return {"ok": True, "path": str(target), "size": len(data)}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}


# JS ที่ inject เข้า webview — intercept คลิกปุ่ม download → ส่ง blob ไป Python
#
# Background bug fix (P1.2 / 2026-05-15 — Coddy #4):
# Streamlit's st.download_button calls m({...}).click() on a <a> created via
# document.createElement('a') ที่ "ไม่ได้ appendChild" เข้า DOM. Click event บน
# DOM-less anchor ไม่ bubble ไปถึง document → addEventListener('click', ...) ไม่ fire
# → WebView2 ไม่มี native download UI → ดาวน์โหลดเงียบๆ ไม่มีอะไรเกิดขึ้น
# Fix: patch HTMLAnchorElement.prototype.click — intercept method โดยตรง
# (ไม่ต้องพึ่ง DOM bubbling)
_DOWNLOAD_BRIDGE_JS = r"""
(function() {
    if (window.__happy_dl_installed) return;
    window.__happy_dl_installed = true;

    function showToast(msg, isError) {
        if (!document.body) return;  // before DOMContentLoaded
        let t = document.getElementById('__happy_toast');
        if (!t) {
            t = document.createElement('div');
            t.id = '__happy_toast';
            t.style.cssText = 'position:fixed;bottom:24px;right:24px;padding:12px 18px;border-radius:10px;color:white;font-weight:600;z-index:99999;box-shadow:0 4px 12px rgba(0,0,0,0.2);font-family:sans-serif;font-size:14px;max-width:380px;';
            document.body.appendChild(t);
        }
        t.style.background = isError ? '#EF4444' : 'linear-gradient(135deg,#FB923C,#EC4899)';
        t.textContent = msg;
        t.style.display = 'block';
        clearTimeout(window.__happy_toast_timer);
        window.__happy_toast_timer = setTimeout(() => { t.style.display = 'none'; }, 4000);
    }

    function parseContentDisposition(cd) {
        // Server ส่งชื่อไฟล์จริงผ่าน header นี้ (Streamlit ใช้แบบ filename="..." plain quoted)
        // รองรับทั้ง RFC 5987 (filename*=UTF-8''...) และ filename="..." / filename=...
        if (!cd) return '';
        let m = cd.match(/filename\*=UTF-8''([^;\r\n]+)/i);
        if (m) {
            try { return decodeURIComponent(m[1].trim()); }
            catch (e) { return m[1].trim(); }
        }
        m = cd.match(/filename="([^"]+)"/i) || cd.match(/filename=([^;\r\n]+)/i);
        return m ? m[1].trim() : '';
    }

    function fallbackFilenameFromUrl(href) {
        try {
            const u = new URL(href, window.location.origin);
            const last = (u.pathname.split('/').pop() || '').split('?')[0];
            return last || 'happy_download.bin';
        } catch (e) {
            return 'happy_download.bin';
        }
    }

    async function handleDownload(href, anchorDownloadAttr) {
        showToast('📥 กำลังเตรียมไฟล์ ...');
        try {
            const resp = await fetch(href);
            if (!resp.ok) {
                showToast('❌ โหลดไฟล์ไม่ได้: HTTP ' + resp.status, true);
                return;
            }
            // เลือกชื่อไฟล์: Content-Disposition (server-side, แม่นสุด)
            //   → anchor's download attribute (ถ้าไม่ว่าง)
            //   → URL pathname (hash — last resort)
            let filename = parseContentDisposition(resp.headers.get('Content-Disposition'));
            if (!filename && anchorDownloadAttr) filename = anchorDownloadAttr;
            if (!filename) filename = fallbackFilenameFromUrl(href);

            showToast('📥 กำลังบันทึก ' + filename + ' ...');
            const blob = await resp.blob();
            const reader = new FileReader();
            reader.onload = async () => {
                const base64 = reader.result.split(',')[1];
                if (!window.pywebview || !window.pywebview.api) {
                    showToast('❌ pywebview API ไม่พร้อม', true);
                    return;
                }
                const result = await window.pywebview.api.save_download(base64, filename);
                if (result && result.ok) {
                    showToast('✅ บันทึกแล้วที่: ' + result.path);
                } else {
                    showToast('❌ บันทึกไม่ได้: ' + (result && result.error || 'unknown'), true);
                }
            };
            reader.readAsDataURL(blob);
        } catch (err) {
            showToast('❌ เกิดข้อผิดพลาด: ' + (err && err.message || err), true);
        }
    }

    // [1] Prototype patch — intercept Streamlit's programmatic a.click() on DOM-less anchors.
    // Streamlit's createDownloadLinkElement() returns <a> created via document.createElement('a')
    // โดยไม่ appendChild → .click() ไม่ bubble ไป document → DOM event listener จับไม่ได้
    const __origAnchorClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function() {
        try {
            const href = this.href || '';
            const hasDownload = this.hasAttribute('download');
            // Intercept ถ้าเป็น download link, blob:, data:, หรือ Streamlit /media/ path
            const isStreamlitMedia = href.indexOf('/media/') !== -1;
            if (hasDownload || href.startsWith('blob:') || href.startsWith('data:') || isStreamlitMedia) {
                handleDownload(href, this.getAttribute('download') || '');
                return;
            }
        } catch (e) {
            // fall through to original behavior
        }
        return __origAnchorClick.apply(this, arguments);
    };

    // [2] DOM event listener — defense in depth สำหรับ <a> ที่อยู่ใน DOM จริง
    // (เช่น link ปกติที่ user คลิกเอง — ไม่ผ่าน .click() programmatic)
    document.addEventListener('click', function(e) {
        const a = e.target && e.target.closest && e.target.closest('a[download], a[href^="blob:"], a[href^="data:"]');
        if (!a) return;
        e.preventDefault();
        e.stopPropagation();
        handleDownload(a.href || '', a.getAttribute('download') || '');
    }, true);
})();
"""


def main():
    import webview  # imported here so error message is clean if missing

    # ถ้ามีคนเปิด Streamlit ค้างอยู่แล้วบนพอร์ตนี้ → ใช้เลยไม่ต้องเปิดใหม่
    proc = None
    streamlit_thread = None
    if not is_port_in_use(PORT):
        if _is_frozen():
            # PyInstaller .exe: รัน Streamlit ใน thread ภายใน process เดียวกัน
            streamlit_thread = threading.Thread(target=start_streamlit_embedded, daemon=True)
            streamlit_thread.start()
        else:
            # Dev mode: รัน Streamlit ใน subprocess (debug ง่ายกว่า)
            proc = start_streamlit_subprocess()

        ready = wait_for_streamlit(timeout=60)
        if not ready:
            if proc:
                proc.terminate()
            print("Streamlit did not start in time. Check Python and dependencies.")
            sys.exit(1)
    else:
        print(f"Port {PORT} already in use — reusing existing Streamlit server.")

    url = f"http://127.0.0.1:{PORT}"
    js_api = _JSApi()
    window = webview.create_window(
        WINDOW_TITLE,
        url=url,
        js_api=js_api,
        width=1280,
        height=820,
        min_size=(900, 600),
        resizable=True,
        text_select=True,
    )

    def on_loaded():
        # ใส่ download bridge ใหม่ทุกครั้งที่ navigate (Streamlit rerun = same URL but new content)
        try:
            window.evaluate_js(_DOWNLOAD_BRIDGE_JS)
        except Exception:
            pass

    window.events.loaded += on_loaded

    def on_closed():
        # ปิด Streamlit subprocess ด้วยตอนปิด window
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    window.events.closed += on_closed

    # ตั้ง icon ของ window (ถ้าเป็นไปได้)
    icon_path = str(ICON_FILE) if ICON_FILE.exists() else None
    webview.start(
        icon=icon_path,
        debug=False,
    )


if __name__ == "__main__":
    main()
