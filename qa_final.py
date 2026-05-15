"""Phase A Final QA — syntax, imports, smoke tests, server health.
No API calls. Run from project root."""
import ast
import sys
import urllib.request
import urllib.error
from pathlib import Path

PROJ = Path(__file__).parent
RESULTS = []


def check(name, ok, note=""):
    RESULTS.append((name, ok, note))
    icon = "PASS" if ok else "FAIL"
    print(f"[{icon}] {name}" + (f" — {note}" if note else ""))


# ─── 1. Syntax ──────────────────────────────────────────────────────────────
print("\n=== 1. Syntax check ===")
PY_FILES = [
    "app.py", "auth.py", "pipeline.py", "agents.py",
    "builder.py", "extractor.py", "file_loader.py", "happy_desktop.py",
]
all_ok = True
for f in PY_FILES:
    path = PROJ / f
    try:
        code = path.read_text(encoding="utf-8")
        ast.parse(code)
        check(f"syntax: {f}", True, f"{len(code.splitlines())} lines")
    except SyntaxError as e:
        check(f"syntax: {f}", False, f"{e.msg} at line {e.lineno}")
        all_ok = False
    except Exception as e:
        check(f"syntax: {f}", False, str(e))
        all_ok = False

if not all_ok:
    print("\n[FATAL] syntax errors — aborting further checks")
    sys.exit(1)

# ─── 2. Import check ────────────────────────────────────────────────────────
print("\n=== 2. Import check ===")
sys.path.insert(0, str(PROJ))
for mod_name in ["auth", "agents", "pipeline", "builder", "extractor", "file_loader"]:
    try:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        __import__(mod_name)
        check(f"import: {mod_name}", True)
    except Exception as e:
        check(f"import: {mod_name}", False, f"{type(e).__name__}: {e}")

# ─── 3. Smoke tests (key functions, no API call) ────────────────────────────
print("\n=== 3. Smoke tests ===")

# Bug 7 — gen_config
try:
    from pipeline import _gen_config
    cfg = _gen_config()
    ok = cfg.max_output_tokens == 65536 and abs(cfg.temperature - 0.4) < 0.01
    check("Bug 7 — _gen_config (65K tokens, 0.4 temp)", ok,
          f"max_tokens={cfg.max_output_tokens}, temp={cfg.temperature}")
except Exception as e:
    check("Bug 7 — _gen_config", False, str(e))

# Bug 8 — _validate_response
try:
    from pipeline import _validate_response
    from types import SimpleNamespace
    # empty → raise
    try:
        _validate_response(SimpleNamespace(text="", candidates=[SimpleNamespace(finish_reason="STOP")]), "x")
        ok = False
    except RuntimeError:
        ok = True
    check("Bug 8 — empty response raises", ok)
except Exception as e:
    check("Bug 8 — _validate_response", False, str(e))

# Bug 10 — parse_judge_score
try:
    from pipeline import parse_judge_score, parse_judge
    ok = parse_judge_score("SCORE: 95/100") == 95 and parse_judge_score("nope") == -1
    check("Bug 10 — parse_judge_score parses int", ok)
    score, _ = parse_judge("DECISION: PASS\nSCORE: 87/100\nINSTRUCTIONS_FOR_CODER:\n- x")
    check("Bug 10 — parse_judge returns (score, instr)", score == 87, f"score={score}")
except Exception as e:
    check("Bug 10 — parse_judge", False, str(e))

# Bug 9 — _validate_project_completeness (using temp session)
try:
    from pipeline import _validate_project_completeness
    import tempfile
    sp = Path(tempfile.mkdtemp(prefix="qa_complete_"))
    (sp / "06_debugger.md").write_text(
        "### File: game.js\n```javascript\nconst c=1;\n```\n",  # js without html → should fail
        encoding="utf-8"
    )
    try:
        _validate_project_completeness(sp)
        check("Bug 9 — JS-only fails completeness", False, "no raise")
    except RuntimeError as e:
        check("Bug 9 — JS-only fails completeness", "no entry-point .html" in str(e))
    import shutil; shutil.rmtree(sp)
except Exception as e:
    check("Bug 9 — _validate_project_completeness", False, str(e))

# Bug 12 — extractor smart defaults
try:
    from extractor import extract_files_from_text
    md = "```html\n<!DOCTYPE html><body><script src='game.js'></script></body></html>\n```\n\n```javascript\nconst c = document.getElementById('x'); requestAnimationFrame(loop);\n```"
    files = extract_files_from_text(md)
    ok = "index.html" in files and "game.js" in files
    check("Bug 12 — smart defaults (index.html + game.js)", ok, f"keys={list(files.keys())}")
except Exception as e:
    check("Bug 12 — extractor", False, str(e))

# Bug 12 — '### File:' heading
try:
    from extractor import extract_files_from_text
    md = "### File: main.py\n```python\nprint('hi')\n```\n"
    files = extract_files_from_text(md)
    check("Bug 12 — '### File:' heading parsed", "main.py" in files,
          f"keys={list(files.keys())}")
except Exception as e:
    check("Bug 12 — '### File:' heading", False, str(e))

# Bug 13 — parse_tester_decision
try:
    from pipeline import parse_tester_decision
    p1, _ = parse_tester_decision("DECISION: PLAYABLE\nSCORE: 95")
    p2, _ = parse_tester_decision("DECISION: BROKEN\nINSTRUCTIONS_FOR_CODER:\n- fix x")
    ok = p1 is True and p2 is False
    check("Bug 13 — parse_tester_decision (PLAYABLE/BROKEN)", ok)
except Exception as e:
    check("Bug 13 — parse_tester_decision", False, str(e))

# Pipeline reorder — IMPL_PHASES order
try:
    from agents import IMPL_PHASES, KICKOFF_PHASES, get_phases_for_mode
    ids = [p["id"] for p in IMPL_PHASES]
    expected = ["pm_kickoff", "architect", "db_admin", "coder", "frontend",
                "tester", "debugger", "judge", "devops", "summarizer", "pm_final"]
    check("Pipeline reorder — Tester before Debugger+Judge", ids == expected,
          f"order={ids[5:8]}")
except Exception as e:
    check("Pipeline reorder", False, str(e))

# Builder — project type detection
try:
    from builder import detect_project_type, _is_test_file
    ok = (detect_project_type({"main.py": ""}) == "python"
          and detect_project_type({"index.html": ""}) == "web"
          and detect_project_type({"data.json": "{}"}) == "unknown"
          and _is_test_file("test_x.py") is True
          and _is_test_file("app.py") is False)
    check("Bug 6 + web build — detect_project_type", ok)
except Exception as e:
    check("Builder detect", False, str(e))

# ─── 4. Server health ───────────────────────────────────────────────────────
print("\n=== 4. Server health ===")
try:
    r = urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=5)
    body = r.read().decode("utf-8", errors="ignore")
    check("Streamlit server", r.status == 200, f"status={r.status}, body={body}")
except urllib.error.URLError as e:
    check("Streamlit server", False, str(e))
except Exception as e:
    check("Streamlit server", False, str(e))

# ─── 5. Auth state (advisory only — user env, not code health) ─────────────
print("\n=== 5. Auth state (advisory — user can re-login via Settings if missing) ===")
auth_path = Path.home() / ".happy" / "auth.json"
exists = auth_path.exists() and auth_path.stat().st_size > 0
if exists:
    print(f"[PASS] auth.json present (login OK)")
else:
    print(f"[WARN] auth.json missing or empty — user needs to paste API key in Settings (lifecycle UI flow tested)")

# ─── Final summary ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PHASE A FINAL QA SUMMARY")
print("=" * 60)
total = len(RESULTS)
passed = sum(1 for _, ok, _ in RESULTS if ok)
print(f"\n  Passed: {passed}/{total}")
for name, ok, note in RESULTS:
    icon = "PASS" if ok else "FAIL"
    print(f"  [{icon}] {name}")

ready = passed == total
print("\n" + ("✅ PHASE A READY TO COMMIT + GO TO PHASE B" if ready
              else "❌ NOT READY — fix failing checks above first"))
sys.exit(0 if ready else 1)
