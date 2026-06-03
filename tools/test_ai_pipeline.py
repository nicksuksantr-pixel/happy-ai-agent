"""
tools/test_ai_pipeline.py — Headless AI tester for HAPPY AI Agent.

ขับ pipeline หลายเอเจนต์ (Gemini) แบบไม่ต้องเปิด GUI — ใช้ verify ว่า
"เอไอทำงาน" ได้จริง end-to-end + เก็บผลรายเฟส + token usage มาดู

วิธีใช้ (รันจาก project root):
    python tools/test_ai_pipeline.py                      # connectivity only (~2 calls, แทบไม่กิน quota)
    python tools/test_ai_pipeline.py --connectivity       # เหมือน default
    python tools/test_ai_pipeline.py --quick "<task>"     # รัน Quick pipeline เต็ม (11 เฟส)
    python tools/test_ai_pipeline.py --thorough "<task>"  # รัน Thorough (18 เฟส)
    python tools/test_ai_pipeline.py --quick "<task>" --delay 5   # override phase delay (เร่งเทส)

อ่าน key จาก ~/.happy/auth.json และ settings จาก ~/.happy/settings.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# รันจาก tools/ ได้ — ดัน project root เข้า sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows console = cp874/cp1252 → กัน UnicodeEncodeError ตอน print emoji/ไทย
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import auth
import pipeline as pl


def _load_settings() -> dict:
    """อ่าน settings ของ user จริง — fallback เป็น DEFAULT_SETTINGS ถ้าไม่มี"""
    from core.config import DEFAULT_SETTINGS
    settings = dict(DEFAULT_SETTINGS)
    path = Path.home() / ".happy" / "settings.json"
    if path.exists():
        try:
            settings.update(json.loads(path.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[warn] อ่าน settings.json ไม่ได้: {e} — ใช้ default")
    return settings


def _build_client():
    key = auth.load_api_key()
    if not key:
        print("❌ ไม่พบ API key ที่ ~/.happy/auth.json — เปิดแอป → Settings → ใส่ key ก่อน")
        return None, None
    masked = key[:6] + "..." + key[-4:]
    print(f"🔑 โหลด key แล้ว: {masked} (format ok: {auth.is_valid_key_format(key)})")
    client, err = auth.create_client(key)
    if err:
        print(f"❌ สร้าง client ไม่ได้: {err}")
        return None, None
    return client, key


def run_connectivity(model: str) -> int:
    """แค่พิสูจน์ว่า key + model + SDK เชื่อม Gemini ได้ (1 list + 1 generate)"""
    print("=" * 64)
    print("CONNECTIVITY TEST — พิสูจน์การเชื่อมต่อ Gemini (ต้นทุนต่ำมาก)")
    print("=" * 64)
    client, _ = _build_client()
    if client is None:
        return 1

    # 1) list models — เหมือน auth.test_connection ของแอป
    t0 = time.time()
    ok, msg = auth.test_connection(client)
    print(f"\n[1] list models  ({time.time()-t0:.1f}s): {msg}")
    if not ok:
        return 1
    models = auth.list_available_models(client)
    present = model in models or any(model in m for m in models)
    print(f"    เจอ text models {len(models)} ตัว · model ที่ตั้งไว้ '{model}' "
          f"{'✅ พร้อมใช้' if present else '⚠️ ไม่อยู่ในลิสต์ (อาจยังเรียกได้)'}")

    # 2) generate_content เล็กๆ 1 ครั้ง — พิสูจน์ว่า "สร้างข้อความ" ได้จริง
    print(f"\n[2] generate_content (model={model}) — prompt สั้นๆ ...")
    try:
        from google.genai.types import GenerateContentConfig
        cfg = GenerateContentConfig(max_output_tokens=20, temperature=0.0)
    except Exception:
        cfg = None
    t0 = time.time()
    try:
        kwargs = {"model": model,
                  "contents": "ตอบกลับด้วยคำเดียวว่า: OK"}
        if cfg is not None:
            kwargs["config"] = cfg
        resp = client.models.generate_content(**kwargs)
    except Exception as e:
        print(f"    ❌ generate ล้มเหลว: {str(e)[:200]}")
        return 1
    text = pl._safe_text(resp)
    usage = pl._extract_usage(resp, "connectivity")
    fr = ""
    try:
        cands = getattr(resp, "candidates", None) or []
        if cands:
            fr = str(getattr(cands[0], "finish_reason", ""))
    except Exception:
        pass
    print(f"    ✅ ตอบกลับ ({time.time()-t0:.1f}s): {text!r}")
    print(f"    finish_reason={fr or '?'} · tokens in/out/total="
          f"{usage['input_tokens']}/{usage['output_tokens']}/{usage['total_tokens']}")
    print("\n🎉 CONNECTIVITY OK — เอไอเชื่อมต่อและสร้างข้อความได้")
    return 0


def run_pipeline(task: str, mode: str, delay_override,
                 judge_override=None, loops_override=None,
                 project_type_override=None) -> int:
    """รัน pipeline จริงแบบ headless + พิมพ์ progress รายเฟส"""
    settings = _load_settings()
    model = settings.get("model", "gemini-3.1-flash-lite-preview")
    delay = delay_override if delay_override is not None else int(settings.get("delay", 45))
    judge_threshold = (judge_override if judge_override is not None
                       else int(settings.get("judge_threshold", 100)))
    max_judge_loops = (loops_override if loops_override is not None
                       else int(settings.get("max_judge_loops", 5)))
    project_type = project_type_override or settings.get("project_type", "html")

    print("=" * 64)
    print(f"PIPELINE TEST — mode={mode} · model={model}")
    print(f"  delay={delay}s · judge_threshold={judge_threshold} · "
          f"max_judge_loops={max_judge_loops} · project_type={project_type}")
    print(f"  task: {task}")
    print("=" * 64)

    client, _ = _build_client()
    if client is None:
        return 1

    state = {"start": time.time(), "n_complete": 0, "n_error": 0, "judge": []}

    def on_start(pid, name, idx):
        print(f"\n▶  [{idx}] {name} ...", flush=True)

    def on_complete(pid, name, idx, output):
        state["n_complete"] += 1
        print(f"✅ {name}  ({len(output):,} chars)", flush=True)

    def on_error(pid, name, err):
        state["n_error"] += 1
        print(f"❌ {name}: {err}", flush=True)

    def on_judge(round_num, decision, score):
        state["judge"].append((round_num, decision, score))
        print(f"   ⚖️ Judge round {round_num}: {decision} {score}/100", flush=True)

    runner = pl.PipelineRunner(
        client, model=model, delay=delay,
        judge_threshold=judge_threshold, max_judge_loops=max_judge_loops,
        mode=mode, project_type=project_type,
        on_phase_start=on_start, on_phase_complete=on_complete,
        on_phase_error=on_error, on_judge_round=on_judge,
    )

    session_path = pl.create_session(task, model, settings)
    print(f"📁 session: {session_path}")

    try:
        runner.run(task, session_path)
    except pl.AuthError as e:
        print(f"\n❌ AUTH ERROR — key ใช้ไม่ได้: {str(e)[:200]}")
        return 1
    except Exception as e:
        print(f"\n❌ pipeline หยุดกลางทาง: {type(e).__name__}: {str(e)[:300]}")
        # ยังพิมพ์สรุปต่อด้านล่าง (เฟสที่เสร็จก่อนพังก็มีค่า)

    # ── สรุปผล ──
    elapsed = time.time() - state["start"]
    tl = runner.token_log
    tot_in = sum(t["input_tokens"] for t in tl)
    tot_out = sum(t["output_tokens"] for t in tl)
    print("\n" + "=" * 64)
    print("สรุปผล")
    print("=" * 64)
    print(f"  เวลา: {elapsed/60:.1f} นาที · เฟสเสร็จ: {state['n_complete']} · error: {state['n_error']}")
    print(f"  Gemini calls: {len(tl)} · tokens in/out: {tot_in:,}/{tot_out:,}")
    if state["judge"]:
        last = state["judge"][-1]
        print(f"  Judge: {len(state['judge'])} รอบ · ล่าสุด {last[1]} {last[2]}/100")
    # extracted files
    try:
        from extractor import extract_from_session
        files = extract_from_session(session_path)
        print(f"  ไฟล์โค้ดที่ได้: {len(files)} → {', '.join(list(files.keys())[:12])}")
    except Exception as e:
        print(f"  (extract ไฟล์ไม่ได้: {str(e)[:120]})")
    # meta warnings
    try:
        meta = json.loads((session_path / "_meta.json").read_text(encoding="utf-8"))
        for k in ("completeness_warning", "tester_warning"):
            if meta.get(k):
                print(f"  ⚠️ {k}: {meta[k]}")
        print(f"  status: {meta.get('status', '?')}")
    except Exception:
        pass
    print(f"\n📁 ผลเต็มอยู่ที่: {session_path}")
    return 0 if state["n_error"] == 0 else 2


def main():
    ap = argparse.ArgumentParser(description="HAPPY headless AI tester")
    ap.add_argument("--connectivity", action="store_true",
                    help="แค่เทสการเชื่อมต่อ (default ถ้าไม่ใส่ task)")
    ap.add_argument("--quick", metavar="TASK", help="รัน Quick pipeline กับ task นี้")
    ap.add_argument("--thorough", metavar="TASK", help="รัน Thorough pipeline กับ task นี้")
    ap.add_argument("--delay", type=int, default=None,
                    help="override phase delay (วินาที) — เร่งเทส")
    ap.add_argument("--judge", type=int, default=None,
                    help="override judge_threshold (เร่งเทสไม่ให้ loop ยาว)")
    ap.add_argument("--loops", type=int, default=None,
                    help="override max_judge_loops")
    ap.add_argument("--project-type", dest="project_type", default=None,
                    help="override project_type (html / desktop_installer)")
    args = ap.parse_args()

    settings = _load_settings()
    model = settings.get("model", "gemini-3.1-flash-lite-preview")

    if args.quick:
        return run_pipeline(args.quick, "quick", args.delay,
                            args.judge, args.loops, args.project_type)
    if args.thorough:
        return run_pipeline(args.thorough, "thorough", args.delay,
                            args.judge, args.loops, args.project_type)
    return run_connectivity(model)


if __name__ == "__main__":
    sys.exit(main())
