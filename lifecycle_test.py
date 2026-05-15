"""End-to-end lifecycle test: login → submit task → wait for pipeline → verify output.
Reads key from ~/.happy/auth.json.before_test (backup), tests UI login flow,
then runs a full pipeline and verifies. ALWAYS restores auth.json on exit.
"""
import json
import shutil
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT = Path(__file__).parent
SCREENS = PROJECT / "ui_screenshots"
SCREENS.mkdir(exist_ok=True)
AUTH = Path.home() / ".happy" / "auth.json"
BACKUP = Path.home() / ".happy" / "auth.json.before_test"

results = []


def add(name, ok, note=""):
    results.append({"test": name, "pass": bool(ok), "note": note})
    icon = "PASS" if ok else "FAIL"
    print(f"[{icon}] {name} - {note}", flush=True)


def shot(page, name):
    try:
        page.screenshot(path=str(SCREENS / f"lifecycle_{name}.png"), full_page=True)
    except Exception as e:
        print(f"  [shot err] {name}: {e}", flush=True)


def run_test():
    if not BACKUP.exists():
        print("[FATAL] backup auth.json.before_test missing — abort", flush=True)
        return

    with open(BACKUP, encoding="utf-8") as f:
        api_key = json.load(f)["api_key"]
    print(f"Key from backup: {api_key[:8]}...{api_key[-4:]}", flush=True)

    # Verify auth.json was deleted by the test setup
    if AUTH.exists():
        print(f"[WARN] auth.json still present — test may not simulate logged-out", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(15000)

        # ─── 1. Open page → expect unauthenticated state ────────────────────
        page.goto("http://127.0.0.1:8501", wait_until="networkidle", timeout=30000)
        time.sleep(4)
        shot(page, "01_login_required")
        body = page.text_content("body") or ""
        unauth = "ยังไม่ได้เชื่อมต่อ" in body
        add("Page shows unauth warning after auth.json deleted", unauth,
            "saw 'ยังไม่ได้เชื่อมต่อ'" if unauth else "no auth warning visible")

        # ─── 2. Navigate to Settings via sidebar ─────────────────────────────
        try:
            page.locator("button:has-text('⚙️ ตั้งค่า')").first.click(force=True, timeout=10000)
            time.sleep(3)
            shot(page, "02_settings_page")
            add("Navigate to Settings", True, "sidebar nav clicked")
        except Exception as e:
            add("Navigate to Settings", False, str(e)[:100])
            browser.close()
            return

        # ─── 3. Paste API key ─────────────────────────────────────────────────
        try:
            key_input = page.locator("input[type='password']").first
            key_input.fill(api_key, timeout=5000)
            time.sleep(1)
            add("Paste API key into settings input", True, "filled")
        except Exception as e:
            add("Paste API key", False, str(e)[:100])
            browser.close()
            return

        # ─── 4. Click save & connect ─────────────────────────────────────────
        try:
            page.locator("button:has-text('บันทึก & เชื่อมต่อ')").first.click(force=True, timeout=10000)
            time.sleep(10)  # wait for test_connection + state update
            shot(page, "03_after_save")
            body = page.text_content("body") or ""
            connected = "เชื่อมต่อแล้ว" in body or "เชื่อมต่อสำเร็จ" in body
            add("Login: connected status shown after save",
                connected, "'เชื่อมต่อแล้ว' or success message found" if connected else "no success msg")
        except Exception as e:
            add("Click save & connect", False, str(e)[:100])
            browser.close()
            return

        # Verify auth.json was created on disk
        time.sleep(2)
        auth_created = AUTH.exists()
        add("auth.json recreated on disk after login",
            auth_created, f"file exists at {AUTH}")

        # ─── 5. Adjust delay slider 60 → 15 (faster test) ─────────────────────
        # Streamlit sliders respond to ArrowLeft/Right when focused.
        # Default delay=60, max=120, min=1. 45 left arrows to reach 15.
        try:
            sliders = page.locator("[role='slider']").all()
            if sliders:
                sliders[0].click(force=True)
                time.sleep(0.5)
                for _ in range(45):
                    page.keyboard.press("ArrowLeft")
                time.sleep(1)
                shot(page, "04_delay_adjusted")
                add("Adjusted delay slider", True, "default 60 → ~15s")
            else:
                add("Adjusted delay slider", False, "no slider found")
        except Exception as e:
            add("Adjust delay slider", False, str(e)[:100])

        # ─── 6. Navigate to Home ─────────────────────────────────────────────
        try:
            page.locator("button:has-text('🏠 หน้าหลัก')").first.click(force=True, timeout=10000)
            time.sleep(3)
            shot(page, "05_home_after_login")
            add("Navigate to Home after login", True, "")
        except Exception as e:
            add("Navigate to Home", False, str(e)[:100])
            browser.close()
            return

        # ─── 7. Fill task + submit ───────────────────────────────────────────
        task = ("เขียน Python function ชื่อ multiply_numbers ที่คูณเลข 2 ตัว "
                "(int หรือ float) มี docstring + 3 test cases ใช้ pytest")
        try:
            textarea = page.locator("textarea").first
            textarea.fill(task, timeout=5000)
            time.sleep(1)
            shot(page, "06_task_filled")
            page.locator("button:has-text('ให้น้องช่วยทำ')").first.click(force=True, timeout=10000)
            time.sleep(6)
            shot(page, "07_running_initial")
            add("Task submitted, pipeline started", True, "running page rendered")
        except Exception as e:
            add("Submit task", False, str(e)[:100])
            browser.close()
            return

        # ─── 8. Wait for completion ──────────────────────────────────────────
        # poll every 30s, max 25 min
        start = time.time()
        completed = False
        last_milestone = ""
        for i in range(50):
            time.sleep(30)
            elapsed = time.time() - start
            body = page.text_content("body") or ""
            # Done indicators
            if "เสร็จเรียบร้อย" in body and "ดาวน์โหลดผลงาน" in body:
                completed = True
                print(f"  [done at {elapsed:.0f}s]", flush=True)
                break
            # Track progress milestone
            mile = "(?)"
            for marker, label in [
                ("PM Final", "pm_final"),
                ("Summarizer", "summarizer"),
                ("DevOps", "devops"),
                ("Tester", "tester"),
                ("Judge", "judge"),
                ("Debugger", "debugger"),
                ("Frontend", "frontend"),
                ("Coder", "coder"),
                ("DB Admin", "db_admin"),
                ("Architect", "architect"),
                ("PM Kickoff", "pm_kickoff"),
            ]:
                if marker in body:
                    mile = label
                    break
            if mile != last_milestone:
                print(f"  [{elapsed:.0f}s] milestone: {mile}", flush=True)
                last_milestone = mile
                if i % 3 == 0:
                    shot(page, f"08_progress_{int(elapsed):04d}s")

        shot(page, "09_final_state")
        add(f"Pipeline completes within ~25min",
            completed, f"elapsed {time.time()-start:.0f}s")

        # ─── 9. Verify output by clicking Architect agent ────────────────────
        if completed:
            try:
                page.locator("button:has-text('Architect')").first.click(force=True, timeout=10000)
                time.sleep(3)
                shot(page, "10_architect_output")
                body = page.text_content("body") or ""
                add("Click Architect → output renders",
                    "Architect" in body and len(body) > 5000,
                    f"body length {len(body)}")
            except Exception as e:
                add("Click Architect output", False, str(e)[:100])

        browser.close()


def main():
    try:
        run_test()
    finally:
        # ALWAYS restore auth.json
        if BACKUP.exists():
            shutil.copy2(BACKUP, AUTH)
            BACKUP.unlink()
            print(f"\n[restore] auth.json restored from backup, backup deleted", flush=True)
        else:
            print(f"\n[restore] backup not found — auth.json may need manual restore", flush=True)

    # Final report
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    print(f"\n=== Lifecycle Summary: {passed}/{total} tests passed ===", flush=True)
    for r in results:
        icon = "PASS" if r["pass"] else "FAIL"
        print(f"  [{icon}] {r['test']}: {r['note']}", flush=True)

    (PROJECT / "lifecycle_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
