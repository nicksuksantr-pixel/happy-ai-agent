"""End-to-end pipeline test — kicks off a real Gemini run on a tiny task.
Used to verify backend after UI refactor. Run from project root."""
import json
import sys
import time
from pathlib import Path

from auth import load_api_key, create_client
from pipeline import PipelineRunner, create_session, load_session

TASK = "เขียน Python function ชื่อ add_numbers ที่บวกเลข 2 ตัว (int หรือ float) มี docstring + 3 test cases ด้วย pytest (test ค่า positive, negative, float)"
MODEL = "gemini-2.5-flash"
DELAY = 15
THRESHOLD = 80


def main():
    print("=" * 60)
    print("HAPPY E2E Pipeline Test")
    print("=" * 60)

    key = load_api_key()
    if not key:
        print("[FATAL] no api key — set via Streamlit Settings first")
        return 1
    print(f"[auth] key: {key[:8]}...{key[-4:]}")

    client, err = create_client(key)
    if err:
        print(f"[FATAL] client: {err}")
        return 1
    print("[auth] client OK")

    settings = {"delay": DELAY, "judge_threshold": THRESHOLD, "max_judge_loops": 5, "mode": "quick"}
    session_path = create_session(TASK, MODEL, settings)
    print(f"[session] {session_path}")

    phase_t0 = {}
    def on_start(pid, name, idx):
        phase_t0[pid] = time.time()
        print(f"[{idx+1:02d}] START   {pid} ({name})", flush=True)

    def on_complete(pid, name, idx, output):
        dur = time.time() - phase_t0.get(pid, time.time())
        print(f"[{idx+1:02d}] DONE    {pid}  +{dur:.1f}s  {len(output)} chars", flush=True)

    def on_error(pid, name, err):
        print(f"[ERR  ] {pid}: {err}", flush=True)

    def on_judge(rnd, dec, score):
        print(f"[JUDGE] round {rnd}: {dec} score={score}", flush=True)

    runner = PipelineRunner(
        client=client, model=MODEL, delay=DELAY,
        judge_threshold=THRESHOLD, max_judge_loops=5, mode="quick",
        on_phase_start=on_start, on_phase_complete=on_complete,
        on_phase_error=on_error, on_judge_round=on_judge,
    )

    print(f"\n=== Pipeline starting: mode=quick model={MODEL} delay={DELAY}s ===\n", flush=True)
    t0 = time.time()
    try:
        runner.run(TASK, session_path)
    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n=== FAILED after {elapsed:.1f}s: {e} ===", flush=True)
        return 2

    elapsed = time.time() - t0
    print(f"\n=== COMPLETED in {elapsed:.1f}s ({elapsed/60:.1f} min) ===", flush=True)

    data = load_session(session_path)
    meta = data["meta"]
    print(f"\n=== Summary ===")
    print(f"  status: {meta.get('status')}")
    print(f"  mode: {meta.get('mode')}")
    print(f"  phases_completed: {len(meta.get('phases_completed', []))}/11")
    print(f"  judge_rounds: {meta.get('judge_rounds')}")
    print(f"  session: {session_path.name}")
    print(f"\n=== Output files ===")
    for f in sorted(session_path.iterdir()):
        print(f"  {f.name}  {f.stat().st_size} bytes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
