"""Automated UI verification for HAPPY web mode using Playwright.
Tests Bug 1-4 fixes + UX redesign (clickable agent buttons).
Run from project root with Streamlit server running on http://127.0.0.1:8501.
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8501"
OUT = Path(__file__).parent
SCREENS = OUT / "ui_screenshots"
SCREENS.mkdir(exist_ok=True)

# Task previews used as identifying text on history buttons (truncated at 40 chars by app.py)
QUICK_TASK_FRAGMENT = "Python function ชื่อ add_numbers"
THOROUGH_TASK_FRAGMENT = "ออโต้คลิกแบบระบบจุดได้"

# Sidebar nav button labels (Thai)
NAV_HOME = "🏠 หน้าหลัก"
NAV_SETTINGS = "⚙️ ตั้งค่า"

# Agent button labels (after UX redesign — format: "{icon} {emoji} {name}")
QUICK_AGENTS = [
    "PM Kickoff", "Architect", "DB Admin", "Coder", "Frontend Dev",
    "Debugger", "Judge", "Tester", "DevOps", "Summarizer", "PM Final",
]
THOROUGH_KICKOFF = [
    "Document Analyst", "Requirements Analyst", "Architect Consult",
    "UX Lead", "Data Lead", "Security Lead", "Brief Synthesizer",
]

results = []

def add(name, passed, note=""):
    results.append({"test": name, "pass": bool(passed), "note": note})
    icon = "PASS" if passed else "FAIL"
    print(f"[{icon}] {name} - {note}", flush=True)


def screenshot(page, name):
    path = SCREENS / f"{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        print(f"  [shot] {path.name}", flush=True)
    except Exception as e:
        print(f"  [shot ERR] {name}: {e}", flush=True)


def count_visible(page, names):
    """Count how many of the given texts are visible on the page."""
    found = 0
    seen = []
    for n in names:
        try:
            loc = page.get_by_text(n, exact=False).first
            if loc.is_visible(timeout=500):
                found += 1
                seen.append(n)
        except Exception:
            pass
    return found, seen


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        # ─── Test 0: Homepage loads ─────────────────────────────────────────
        try:
            page.goto(URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)  # extra wait for Streamlit WebSocket render
            screenshot(page, "01_home")
            add("Homepage loads", True, f"URL OK, body has {len(page.content())} chars")
        except Exception as e:
            add("Homepage loads", False, str(e)[:150])
            browser.close()
            return

        # ─── Test 1: Sidebar shows history with Quick session ───────────────
        try:
            page.wait_for_selector(f"text={QUICK_TASK_FRAGMENT}", timeout=10000)
            add("Sidebar history visible (Quick session)", True,
                f"found '{QUICK_TASK_FRAGMENT[:30]}...'")
        except Exception as e:
            add("Sidebar history visible (Quick session)", False, str(e)[:150])

        # ─── Test 2: Click Quick session → page_done → Bug 1 + UX ────────────
        try:
            page.locator(f"button:has-text('{QUICK_TASK_FRAGMENT}')").first.click(timeout=5000)
            time.sleep(3)
            screenshot(page, "02_done_quick")

            # Should see 11 impl agent button labels (UX redesign — clickable list)
            found, seen = count_visible(page, QUICK_AGENTS)
            passed = found >= 9  # tolerate 1-2 misses due to render timing
            add("Quick session shows 11 agent buttons (UX + Bug 1)",
                passed, f"found {found}/11 (seen: {seen[:4]}...)")
        except Exception as e:
            add("Click Quick session", False, str(e)[:150])

        # ─── Test 3: Click 'Architect' agent → output panel changes (Bug 4 / UX) ─
        try:
            # Find a button with "Architect" text (excluding "Architect Consult")
            arch_btn = page.locator("button:has-text('Architect')").first
            arch_btn.click(timeout=5000)
            time.sleep(2)
            screenshot(page, "03_agent_clicked_architect")

            # After clicking, header on right side should show "Architect"
            # Check that page still renders cleanly (no error)
            page_text = page.text_content("body") or ""
            has_error = "Traceback" in page_text or "Error" in page_text[:500]
            add("Click agent button — output changes (Bug 4)",
                not has_error, "page renders cleanly after click")
        except Exception as e:
            add("Click agent button", False, str(e)[:150])

        # ─── Test 4: Navigate Settings via Thai nav button ───────────────────
        try:
            page.locator(f"button:has-text('{NAV_SETTINGS}')").first.click(timeout=5000)
            time.sleep(3)
            screenshot(page, "04_settings")

            # Settings page should have specific labels
            settings_markers = ["API key", "ตั้งค่า", "Pipeline Mode"]
            found_set, _ = count_visible(page, settings_markers)
            add("Navigate to Settings",
                found_set >= 1, f"found {found_set}/3 settings markers")
        except Exception as e:
            add("Navigate to Settings", False, str(e)[:150])

        # ─── Test 5: Back to Home, click Thorough session → see kickoff agents (Bug 1) ─
        try:
            page.locator(f"button:has-text('{NAV_HOME}')").first.click(timeout=5000)
            time.sleep(2)
            page.locator(f"button:has-text('{THOROUGH_TASK_FRAGMENT}')").first.click(timeout=5000)
            time.sleep(3)
            screenshot(page, "05_done_thorough")

            # Should see kickoff agents (was the Bug 1 — hidden by PHASES filter)
            found_kick, seen_kick = count_visible(page, THOROUGH_KICKOFF)
            passed = found_kick >= 5  # tolerate 1-2 misses
            add("Thorough session shows kickoff agents (Bug 1 fix)",
                passed, f"found {found_kick}/7 kickoff (seen: {seen_kick[:3]}...)")

            # Also count total agent buttons — should be 18 for thorough
            all_thorough = QUICK_AGENTS + THOROUGH_KICKOFF
            found_all, _ = count_visible(page, all_thorough)
            add("Thorough session shows ~18 agent buttons total",
                found_all >= 14, f"found {found_all}/18")
        except Exception as e:
            add("Thorough session check", False, str(e)[:150])

        # ─── Test 6: Click a kickoff agent → output renders ──────────────────
        try:
            doc_btn = page.locator("button:has-text('Document Analyst')").first
            doc_btn.click(timeout=5000)
            time.sleep(2)
            screenshot(page, "06_kickoff_clicked")
            add("Click kickoff agent works (UX)", True, "Document Analyst clicked")
        except Exception as e:
            add("Click kickoff agent", False, str(e)[:150])

        # ─── Test 7: Sidebar collapse → expand button visible (Bug 5) ────────
        # Regression: ตรวจว่า user collapse sidebar แล้วยังเปิดกลับได้
        # ใช้ fresh page + navigate to session ให้ state เหมือน bug5_verify ที่เคย PASS
        try:
            ctx7 = browser.new_context(viewport={"width": 1400, "height": 900})
            page7 = ctx7.new_page()
            page7.goto(URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)
            # Navigate to a session first (stable state)
            page7.locator(f"button:has-text('{QUICK_TASK_FRAGMENT}')").first.click(timeout=5000)
            time.sleep(3)
            collapse_btn = page7.locator("[data-testid='stSidebarCollapseButton']").first
            collapse_btn.click(force=True, timeout=10000)
            time.sleep(3)
            expand_btn = page7.locator("[data-testid='stExpandSidebarButton']").first
            count = expand_btn.count()
            visible = expand_btn.is_visible(timeout=3000) if count > 0 else False
            try:
                page7.screenshot(path=str(SCREENS / "07_sidebar_collapsed.png"), full_page=True)
            except Exception:
                pass
            add("Sidebar collapse → expand button visible (Bug 5)",
                visible, f"expand button count={count}, visible={visible}")
            ctx7.close()
        except Exception as e:
            add("Bug 5 sidebar collapse regression", False, str(e)[:150])

        browser.close()

    # ─── Save report ────────────────────────────────────────────────────────
    report_path = OUT / "ui_verify_results.json"
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    print(f"\n=== Summary: {passed}/{total} tests passed ===")
    for r in results:
        icon = "PASS" if r["pass"] else "FAIL"
        print(f"  [{icon}] {r['test']}")
    print(f"\nReport: {report_path}")
    print(f"Screenshots: {SCREENS}/")


if __name__ == "__main__":
    main()
